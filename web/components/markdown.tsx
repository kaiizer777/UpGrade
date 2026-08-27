"use client";

import * as React from "react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Check, Copy, Terminal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface CodeBlockProps {
  language?: string;
  code: string;
}

function CodeBlock({ language, code }: CodeBlockProps) {
  const [hasCopied, setHasCopied] = useState(false);

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setHasCopied(true);
      setTimeout(() => setHasCopied(false), 2000);
    } catch {
      // Fallback or ignore clipboard error
    }
  };

  return (
    <div className="my-2.5 overflow-hidden rounded-lg border border-border/80 bg-muted/60 font-mono text-xs shadow-xs">
      <div className="flex items-center justify-between border-b border-border/60 bg-muted px-3 py-1.5 text-[11px] font-medium text-muted-foreground">
        <span className="flex items-center gap-1.5 uppercase tracking-wider font-semibold">
          <Terminal className="size-3 text-primary" aria-hidden="true" />
          {language || "code"}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          onClick={copyToClipboard}
          className="h-6 w-6 text-muted-foreground hover:text-foreground"
          aria-label="Copy code to clipboard"
        >
          {hasCopied ? (
            <Check className="size-3 text-emerald-500" />
          ) : (
            <Copy className="size-3" />
          )}
        </Button>
      </div>
      <pre className="overflow-x-auto p-3 text-foreground selection:bg-primary/20">
        <code>{code}</code>
      </pre>
    </div>
  );
}

export interface MarkdownProps {
  content: string;
  className?: string;
}

export function Markdown({ content, className }: MarkdownProps) {
  return (
    <div className={cn("text-xs sm:text-sm leading-relaxed text-foreground space-y-2", className)}>
      <ReactMarkdown
        components={{
          p({ children }) {
            return <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>;
          },
          h1({ children }) {
            return (
              <h3 className="font-heading text-base font-bold tracking-tight text-foreground mt-3 mb-1">
                {children}
              </h3>
            );
          },
          h2({ children }) {
            return (
              <h4 className="font-heading text-sm font-semibold tracking-tight text-foreground mt-2.5 mb-1">
                {children}
              </h4>
            );
          },
          h3({ children }) {
            return (
              <h5 className="font-heading text-xs font-semibold tracking-tight text-foreground mt-2 mb-0.5 uppercase">
                {children}
              </h5>
            );
          },
          ul({ children }) {
            return <ul className="list-disc pl-4 space-y-1 my-1.5">{children}</ul>;
          },
          ol({ children }) {
            return <ol className="list-decimal pl-4 space-y-1 my-1.5">{children}</ol>;
          },
          li({ children }) {
            return <li className="leading-relaxed">{children}</li>;
          },
          blockquote({ children }) {
            return (
              <blockquote className="border-l-2 border-primary/60 bg-muted/30 pl-3 py-1 my-2 text-xs italic text-muted-foreground rounded-r">
                {children}
              </blockquote>
            );
          },
          a({ href, children }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline underline-offset-2 hover:text-primary/80 font-medium"
              >
                {children}
              </a>
            );
          },
          code({ className: codeClass, children }) {
            const match = /language-(\w+)/.exec(codeClass || "");
            const codeString = String(children).replace(/\n$/, "");
            const isMultiline = codeString.includes("\n") || Boolean(match);

            if (isMultiline) {
              return <CodeBlock language={match ? match[1] : undefined} code={codeString} />;
            }

            return (
              <code className="rounded border border-border/60 bg-muted/80 px-1.5 py-0.5 font-mono text-[11px] sm:text-xs font-semibold text-foreground selection:bg-primary/20">
                {children}
              </code>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
