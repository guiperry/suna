import React from 'react';
import { ToolViewProps } from './types';
import { formatTimestamp, getToolTitle } from './utils';
import { getToolIcon } from '../utils';
import { CircleDashed, CheckCircle, AlertTriangle } from 'lucide-react';
import { Markdown } from '@/components/ui/markdown';
import { cn } from '@/lib/utils';

export function GenericToolView({
  name = 'unknown',
  assistantContent,
  toolContent,
  isSuccess = true,
  isStreaming = false,
  assistantTimestamp,
  toolTimestamp,
}: ToolViewProps) {
  console.log('GenericToolView:', {
    name,
    assistantContent,
    toolContent,
    isSuccess,
    isStreaming,
    assistantTimestamp,
    toolTimestamp,
  });

  const toolTitle = getToolTitle(name);
  const Icon = getToolIcon(name);

  // Format content for display
  const formatContent = (content: string | null | any) => {
    if (!content) return null;

    // If content is already an object (not a string), stringify it
    if (typeof content !== 'string') {
      return JSON.stringify(content, null, 2);
    }

    try {
      // First attempt: try parsing as is (in case it's a regular JSON string)
      try {
        const parsedJson = JSON.parse(content);
        return JSON.stringify(parsedJson, null, 2);
      } catch (e) {
        // Second attempt: handle double-escaped JSON
        // This happens when content is a string that contains a JSON string
        // e.g. "{\"key\":\"value\"}" instead of {"key":"value"}
        try {
          // Try to detect if this is a double-escaped JSON string
          if (content.startsWith('"') && content.endsWith('"') && content.includes('\\\"')) {
            // Parse the outer JSON string to get the inner JSON string
            const innerJsonString = JSON.parse(content);
            if (typeof innerJsonString === 'string') {
              try {
                // Try to parse the inner JSON string
                const innerJson = JSON.parse(innerJsonString);
                return JSON.stringify(innerJson, null, 2);
              } catch {
                // If inner string isn't valid JSON, just return the unescaped string
                return innerJsonString;
              }
            }
          }
        } catch {
          // Ignore errors in the double-escape handling
        }
      }
      
      // If all parsing attempts fail, return as is
      return content;
    } catch (e) {
      // If any error occurs in the overall process, return as is
      console.warn('Error formatting tool content:', e);
      return content;
    }
  };

  // Format the contents
  const formattedAssistantContent = React.useMemo(
    () => formatContent(assistantContent),
    [assistantContent],
  );
  const formattedToolContent = React.useMemo(
    () => formatContent(toolContent),
    [toolContent],
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 p-4 overflow-auto">
        {/* Assistant Content */}
        {assistantContent && !isStreaming && (
          <div className="space-y-1.5">
            <div className="flex justify-between items-center">
              <div className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                Input
              </div>
              {assistantTimestamp && (
                <div className="text-xs text-zinc-500 dark:text-zinc-400">
                  {formatTimestamp(assistantTimestamp)}
                </div>
              )}
            </div>
            <div className="rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3">
              <Markdown className="text-xs text-zinc-800 dark:text-zinc-300">
                {formattedAssistantContent}
              </Markdown>
            </div>
          </div>
        )}

        {/* Tool Result */}
        {toolContent && (
          <div className="space-y-1.5 mt-4">
            <div className="flex justify-between items-center">
              <div className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                {isStreaming ? 'Processing' : 'Output'}
              </div>
              {toolTimestamp && !isStreaming && (
                <div className="text-xs text-zinc-500 dark:text-zinc-400">
                  {formatTimestamp(toolTimestamp)}
                </div>
              )}
            </div>
            <div
              className={cn(
                'rounded-md border p-3',
                isStreaming
                  ? 'border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-900/10'
                  : isSuccess
                    ? 'border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900'
                    : 'border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/10',
              )}
            >
              {isStreaming ? (
                <div className="flex items-center gap-2 text-xs font-medium text-blue-700 dark:text-blue-400">
                  <CircleDashed className="h-3 w-3 animate-spin" />
                  <span>Executing {toolTitle.toLowerCase()}...</span>
                </div>
              ) : (
                <Markdown className="text-xs text-zinc-800 dark:text-zinc-300">
                  {formattedToolContent}
                </Markdown>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-zinc-200 dark:border-zinc-800">
        <div className="flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400">
          {!isStreaming && (
            <div className="flex items-center gap-2">
              {isSuccess ? (
                <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
              ) : (
                <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
              )}
              <span>
                {isSuccess ? 'Completed successfully' : 'Execution failed'}
              </span>
            </div>
          )}

          {isStreaming && (
            <div className="flex items-center gap-2">
              <CircleDashed className="h-3.5 w-3.5 text-blue-500 animate-spin" />
              <span>Processing...</span>
            </div>
          )}

          <div className="text-xs">
            {toolTimestamp && !isStreaming
              ? formatTimestamp(toolTimestamp)
              : assistantTimestamp
                ? formatTimestamp(assistantTimestamp)
                : ''}
          </div>
        </div>
      </div>
    </div>
  );
}
