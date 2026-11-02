import { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Renders markdown and turns valid [n] markers into clickable citation buttons.
 * Only markers that match a citation for this message are linked, so invented
 * source numbers stay as plain text.
 */
export default function MarkdownContent({ content, citations = [], onCitationClick }) {
  const transformed = useMemo(() => {
    if (!content) return '';
    if (!citations.length) return content;
    const known = new Set(citations.map((citation) => citation.number));
    return content.replace(/\[(\d{1,2})\]/g, (match, digits) => {
      const number = Number(digits);
      return known.has(number) ? `[${number}](#cite-${number})` : match;
    });
  }, [content, citations]);

  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children, ...props }) => {
            if (href?.startsWith('#cite-')) {
              const number = Number(href.replace('#cite-', ''));
              return (
                <button
                  type="button"
                  className="citation-marker"
                  onClick={() => onCitationClick?.(number)}
                  title={`Show source ${number}`}
                >
                  {children}
                </button>
              );
            }
            return (
              <a href={href} target="_blank" rel="noreferrer noopener" {...props}>
                {children}
              </a>
            );
          },
        }}
      >
        {transformed}
      </ReactMarkdown>
    </div>
  );
}
