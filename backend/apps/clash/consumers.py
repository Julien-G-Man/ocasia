"""
Clash WebSocket consumer.

Game flow:
  connect  → join channel group, broadcast updated lobby
  start_game (host only) → countdown → question loop → finish
  submit_answer → score update; game loop drives question endings
  disconnect → leave group, update lobby

Redis keys (TTL 2h):
  clash_state_{room_code}    — live game state dict
  clash_presence_{room_code} — {user_id: username} online map
"""
import asyncio
import logging
import time
from typing import ClassVar
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.cache import cache
from django.utils import timezone
from rest_framework.authtoken.models import Token

from .models import ClashRoom, ClashParticipant

logger = logging.getLogger(__name__)

BASE_POINTS = 1000
SPEED_BONUS_MAX = 500
COUNTDOWN_SECONDS = 3
ANSWER_REVEAL_SECONDS = 10  # pause between question end and next question
POLL_INTERVAL = 1.0         # how often the game loop checks if all answered


class ClashConsumer(AsyncJsonWebsocketConsumer):

    # Keyed by room_code. Survives individual connection disconnect/reconnect
    # within the same worker process (single-process dev; Redis layer for prod).
    _game_tasks: ClassVar[dict] = {}

    # ─────────────────────────── Lifecycle ───────────────────────────

    async def connect(self):
        self.room_code = self.scope['url_route']['kwargs']['room_code'].upper()
        self.group_name = f'clash_{self.room_code}'
        self.user = None
        self.room = None
        self.connected = False

        # Token auth via query param  ?token=<key>
        token_key = self._get_token()
        if not token_key:
            await self.close(code=4001)
            return
        self.user = await self._auth_token(token_key)
        if not self.user:
            await self.close(code=4001)
            return

        # Validate room
        try:
            self.room = await sync_to_async(
                ClashRoom.objects.select_related('host').get
            )(room_code=self.room_code)
        except ClashRoom.DoesNotExist:
            await self.close(code=4004)
            return

        if self.room.status == ClashRoom.FINISHED:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        self.connected = True

        await self._set_presence(True)
        # Only broadcast lobby updates while in the waiting room; during an
        # active game everyone is on the play screen, not the lobby.
        if self.room.status == ClashRoom.WAITING:
            await self._broadcast_lobby()

        # If game is already running, immediately catch up this player
        if self.room.status == ClashRoom.ACTIVE:
            state = await self._get_state()
            if state:
                q_idx = state.get('current_question', 0)
                questions = self.room.questions
                if 0 <= q_idx < len(questions):
                    q = questions[q_idx]
                    elapsed = time.time() - state.get('question_start_time', time.time())
                    remaining = max(0.0, self.room.time_per_question - elapsed)
                    await self.send_json({
                        'type': 'game_catchup',
                        'index': q_idx,
                        'total': len(questions),
                        'question': q.get('question', ''),
                        'options': q.get('options', []),
                        'time_limit': self.room.time_per_question,
                        'time_remaining': remaining,
                        'scores': state.get('scores', {}),
                    })

    async def disconnect(self, close_code):
        self.connected = False
        if self.user:
            await self._set_presence(False)
            if self.room and self.room.status == ClashRoom.WAITING:
                await self._broadcast_lobby()

        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content):
        msg_type = content.get('type')
        if msg_type == 'start_game':
            await self.handle_start_game()
        elif msg_type == 'submit_answer':
            await self.handle_submit_answer(content)

    # ─────────────────────────── Client message handlers ───────────────────────────

    async def handle_start_game(self):
        # Re-fetch to get fresh status
        self.room = await sync_to_async(
            ClashRoom.objects.get
        )(pk=self.room.pk)

        if self.room.status != ClashRoom.WAITING:
            await self.send_json({'type': 'error', 'message': 'Game already started.'})
            return

        is_host = await sync_to_async(
            ClashParticipant.objects.filter(
                room=self.room, user=self.user, is_host=True
            ).exists
        )()
        if not is_host:
            await self.send_json({'type': 'error', 'message': 'Only the host can start the Clash.'})
            return

        # Mark active
        self.room.status = ClashRoom.ACTIVE
        self.room.started_at = timezone.now()
        await sync_to_async(self.room.save)()

        await self._init_game_state()

        await self.channel_layer.group_send(self.group_name, {
            'type': 'clash.game_starting',
            'countdown': COUNTDOWN_SECONDS,
        })

        task = asyncio.create_task(self._game_loop())
        ClashConsumer._game_tasks[self.room_code] = task

    async def handle_submit_answer(self, content):
        state = await self._get_state()
        if not state:
            return

        q_idx = content.get('question_index')
        answer = str(content.get('answer', '')).strip()

        # Reject stale / out-of-order answers
        if q_idx != state.get('current_question'):
            return

        user_id = str(self.user.id)
        if user_id in state.get('answered', {}):
            return  # already submitted

        questions = self.room.questions
        if q_idx >= len(questions):
            return

        correct_answer = questions[q_idx].get('answer', '').strip()
        is_correct = answer.lower() == correct_answer.lower()

        # Elapsed time computed server-side from the recorded question start timestamp.
        # Never trust client-supplied elapsed_ms — a cheating client could send 0
        # to always claim the maximum speed bonus.
        question_start = state.get('question_start_time', time.time())
        elapsed_s = min(time.time() - question_start, self.room.time_per_question)
        points = 0
        if is_correct:
            time_ratio = max(0.0, 1.0 - elapsed_s / self.room.time_per_question)
            points = BASE_POINTS + int(SPEED_BONUS_MAX * time_ratio)

        # Atomic-ish update in Redis
        state['answered'][user_id] = {'correct': is_correct, 'points': points}
        state['scores'][user_id] = state['scores'].get(user_id, 0) + points

        ua = state.setdefault('user_answers', {})
        if user_id not in ua:
            ua[user_id] = []
        ua[user_id].append({'q_idx': q_idx, 'correct': is_correct, 'points': points})

        await self._set_state(state)

        # Private confirmation — only this player sees this
        await self.send_json({
            'type': 'answer_confirmed',
            'correct': is_correct,
            'points_earned': points,
            'total_score': state['scores'][user_id],
            'correct_answer': correct_answer,
        })

    # ─────────────────────────── Game loop ───────────────────────────

    async def _game_loop(self):
        """Drives the entire game: countdown → questions → finish."""
        try:
            await asyncio.sleep(COUNTDOWN_SECONDS)

            questions = self.room.questions

            for idx in range(len(questions)):
                await self._broadcast_question(idx)

                # Re-fetch count each question so disconnected players don't stall the game
                participant_count = await sync_to_async(self.room.participants.count)()
                deadline = time.monotonic() + self.room.time_per_question + 1

                while time.monotonic() < deadline:
                    await asyncio.sleep(POLL_INTERVAL)
                    state = await self._get_state()
                    if not state:
                        return
                    if len(state.get('answered', {})) >= participant_count:
                        break

                state = await self._get_state()
                if state:
                    await self._broadcast_question_end(state, idx)

                await asyncio.sleep(ANSWER_REVEAL_SECONDS)

            await self._finish_game()
        except asyncio.CancelledError:
            pass
        finally:
            ClashConsumer._game_tasks.pop(self.room_code, None)

    async def _broadcast_question(self, idx):
        state = await self._get_state()
        if not state:
            return

        state['current_question'] = idx
        state['answered'] = {}
        state['question_start_time'] = time.time()
        await self._set_state(state)

        q = self.room.questions[idx]
        await self.channel_layer.group_send(self.group_name, {
            'type': 'clash.new_question',
            'index': idx,
            'total': len(self.room.questions),
            'question': q.get('question', ''),
            'options': q.get('options', []),
            'time_limit': self.room.time_per_question,
            'server_time': time.time(),
        })

    async def _broadcast_question_end(self, state, idx):
        # Guard: broadcast only once per question index
        if state.get('ended_question') == idx:
            return
        state['ended_question'] = idx
        await self._set_state(state)

        q = self.room.questions[idx]
        scores = state.get('scores', {})
        ranking = await self._build_ranking(scores)

        await self.channel_layer.group_send(self.group_name, {
            'type': 'clash.question_ended',
            'index': idx,
            'correct_answer': q.get('answer', ''),
            'explanation': q.get('explanation', ''),
            'top3': ranking[:3],
            'your_scores': scores,   # client uses own user_id to look up their score
        })

    async def _finish_game(self):
        state = await self._get_state()
        scores = state.get('scores', {}) if state else {}
        ranking = await self._build_ranking(scores)

        # Persist final scores
        await self._save_final_scores(scores, ranking, state)

        self.room.status = ClashRoom.FINISHED
        self.room.finished_at = timezone.now()
        await sync_to_async(self.room.save)()

        await self.channel_layer.group_send(self.group_name, {
            'type': 'clash.game_finished',
            'rankings': ranking,
            'room_code': self.room_code,
        })

    # ─────────────────────────── Channel layer event handlers ───────────────────────────
    # Each method name maps to the 'type' field in group_send, with dots → underscores.

    async def _safe_send(self, event):
        if not self.connected:
            return
        try:
            await self.send_json(event)
        except Exception:
            pass

    async def clash_game_starting(self, event):
        await self._safe_send(event)

    async def clash_new_question(self, event):
        await self._safe_send(event)

    async def clash_question_ended(self, event):
        await self._safe_send(event)

    async def clash_game_finished(self, event):
        await self._safe_send(event)

    async def clash_player_joined(self, event):
        await self._safe_send(event)

    # ─────────────────────────── Helpers ───────────────────────────

    def _get_token(self):
        qs = parse_qs(self.scope.get('query_string', b'').decode())
        tokens = qs.get('token', [])
        return tokens[0] if tokens else None

    @sync_to_async
    def _auth_token(self, key):
        try:
            token = Token.objects.select_related('user').get(key=key)
            if token.user.is_active:
                return token.user
        except Token.DoesNotExist:
            pass
        return None

    def _state_key(self):
        return f'clash_state_{self.room_code}'

    def _presence_key(self):
        return f'clash_presence_{self.room_code}'

    async def _init_game_state(self):
        state = {
            'status': 'active',
            'current_question': -1,
            'answered': {},
            'scores': {},
            'ended_question': -1,
            'user_answers': {},   # {user_id: [{q_idx, correct, points}]}
        }
        await sync_to_async(cache.set)(self._state_key(), state, timeout=7200)

    async def _get_state(self):
        return await sync_to_async(cache.get)(self._state_key())

    async def _set_state(self, state):
        await sync_to_async(cache.set)(self._state_key(), state, timeout=7200)

    async def _set_presence(self, online: bool):
        presence = await sync_to_async(cache.get)(self._presence_key()) or {}
        uid = str(self.user.id)
        if online:
            presence[uid] = self.user.username
        else:
            presence.pop(uid, None)
        await sync_to_async(cache.set)(self._presence_key(), presence, timeout=7200)

    async def _broadcast_lobby(self):
        """Broadcast current participant list to all in the group."""
        participants = await sync_to_async(list)(
            ClashParticipant.objects.filter(room=self.room).select_related('user')
        )
        await self.channel_layer.group_send(self.group_name, {
            'type': 'clash.player_joined',
            'participants': [
                {
                    'username': p.user.username,
                    'display_name': p.display_name,
                    'is_host': p.is_host,
                    'profile_image': p.user.profile_image or '',
                }
                for p in participants
            ],
            'count': len(participants),
        })

    async def _build_ranking(self, scores: dict) -> list:
        participants = await sync_to_async(list)(
            ClashParticipant.objects.filter(room=self.room).select_related('user')
        )
        ranking = sorted(
            [
                {
                    'user_id': str(p.user.id),
                    'username': p.user.username,
                    'display_name': p.display_name,
                    'score': scores.get(str(p.user.id), 0),
                    'profile_image': p.user.profile_image or '',
                }
                for p in participants
            ],
            key=lambda x: x['score'],
            reverse=True,
        )
        for i, entry in enumerate(ranking):
            entry['rank'] = i + 1
        return ranking

    async def _save_final_scores(self, scores: dict, ranking: list, state: dict = None):
        rank_map = {e['user_id']: e['rank'] for e in ranking}
        user_answers_map = (state or {}).get('user_answers', {})
        participants = await sync_to_async(list)(
            ClashParticipant.objects.filter(room=self.room)
        )
        for p in participants:
            uid = str(p.user_id)
            p.score = scores.get(uid, 0)
            p.rank = rank_map.get(uid)
            p.answers = user_answers_map.get(uid, [])
        await sync_to_async(
            ClashParticipant.objects.bulk_update
        )(participants, ['score', 'rank', 'answers'])
