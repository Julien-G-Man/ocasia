import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import 'katex/dist/katex.min.css';

// Allow className on every element (needed for md-* CSS classes).
// Everything else follows the strict defaultSchema allowlist.
// Sanitize runs BEFORE rehypeKatex so KaTeX's own output is never stripped.
const sanitizeSchema = {
    ...defaultSchema,
    attributes: {
        ...defaultSchema.attributes,
        '*': [...(defaultSchema.attributes?.['*'] ?? []), 'className'],
    },
};
import './richText.css';
import { normalizeScientificText } from './scientificText';

const defaultMarkdownComponents = (inline = false) => ({
    p: ({ node, ...props }) => (inline ? <span className="md-p md-p-inline" {...props} /> : <p className="md-p" {...props} />),
    strong: ({ node, ...props }) => <strong className="md-strong" {...props} />,
    em: ({ node, ...props }) => <em className="md-em" {...props} />,
    ul: ({ node, ...props }) => <ul className="md-ul" {...props} />,
    ol: ({ node, ...props }) => <ol className="md-ol" {...props} />,
    li: ({ node, ...props }) => <li className="md-li" {...props} />,
    h1: ({ node, children, ...props }) => <h1 className="md-h1" {...props}>{children}</h1>,
    h2: ({ node, children, ...props }) => <h2 className="md-h2" {...props}>{children}</h2>,
    h3: ({ node, children, ...props }) => <h3 className="md-h3" {...props}>{children}</h3>,
    h4: ({ node, children, ...props }) => <h4 className="md-h4" {...props}>{children}</h4>,
    blockquote: ({ node, ...props }) => <blockquote className="md-blockquote" {...props} />,
    code: ({ node, inline, className, children, ...props }) => {
        const text = String(children).replace(/\n$/, '');

        if (inline) {
            return <code className="md-code-inline" {...props}>{text}</code>;
        }

        return <code className={`md-code-block ${className || ''}`.trim()} {...props}>{text}</code>;
    },
    pre: ({ node, ...props }) => <pre className="md-pre" {...props} />,
    a: ({ node, children, ...props }) => <a className="md-a" target="_blank" rel="noopener noreferrer" {...props}>{children}</a>,
    hr: ({ node, ...props }) => <hr className="md-hr" {...props} />,
    table: ({ node, ...props }) => (
        <div className="chatbot-table-scroll">
            <table className="chatbot-table" {...props} />
        </div>
    ),
    thead: ({ node, ...props }) => <thead className="chatbot-thead" {...props} />,
    tbody: ({ node, ...props }) => <tbody className="chatbot-tbody" {...props} />,
    th: ({ node, ...props }) => <th className="chatbot-th" {...props} />,
    td: ({ node, ...props }) => <td className="chatbot-td" {...props} />,
});

export const normalizeRichTextContent = (text, { normalizeMath = true } = {}) => {
    if (!text) return '';

    const content = String(text)
        .replace(/\r\n/g, '\n')
        .replace(/<br\s*\/?>/gi, '\n')
        .replace(/<\/br>/gi, '\n');
    return normalizeMath ? normalizeScientificText(content) : content;
};

export const getRichTextMarkdownComponents = (options = {}) => {
    const { inline = false, components = {} } = options;
    return {
        ...defaultMarkdownComponents(inline),
        ...components,
    };
};

const RichTextRenderer = ({
    text,
    className = '',
    inline = false,
    normalizeMath = true,
    components = {},
    ...wrapperProps
}) => {
    const content = normalizeRichTextContent(text, { normalizeMath });

    if (!content) return null;

    const Wrapper = inline ? 'span' : 'div';
    const wrapperClassName = ['rich-text-content', inline ? 'rich-text-inline' : 'rich-text-block', className]
        .filter(Boolean)
        .join(' ');

    return (
        <Wrapper className={wrapperClassName} {...wrapperProps}>
            <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[[rehypeSanitize, sanitizeSchema], rehypeKatex]}
                components={getRichTextMarkdownComponents({ inline, components })}
            >
                {content}
            </ReactMarkdown>
        </Wrapper>
    );
};

export default RichTextRenderer;