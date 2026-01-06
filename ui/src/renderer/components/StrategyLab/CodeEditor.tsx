/**
 * Titan-Quant Strategy Code Editor Component
 * 
 * Monaco Editor integration for Python strategy development.
 * Features:
 * - Python syntax highlighting
 * - Auto-completion for strategy APIs
 * - Code snippets for common patterns
 * 
 * Requirements: 8.1
 */

import React, { useRef, useEffect, useCallback, useState } from 'react';
import * as monaco from 'monaco-editor';
import { useTranslation } from 'react-i18next';
import { CodeEditorProps, PythonSuggestion, STRATEGY_TEMPLATE_SNIPPETS } from './types';
import './CodeEditor.css';

// Python keywords for syntax highlighting
const PYTHON_KEYWORDS = [
  'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
  'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from',
  'global', 'if', 'import', 'in', 'is', 'lambda', 'nonlocal', 'not',
  'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 'yield',
  'True', 'False', 'None',
];

// Strategy API suggestions for auto-completion
const STRATEGY_API_SUGGESTIONS: PythonSuggestion[] = [
  // CtaTemplate methods
  {
    label: 'on_init',
    kind: 'function',
    insertText: 'def on_init(self):\n    """Strategy initialization"""\n    ${1:pass}',
    documentation: 'Called when strategy is initialized',
    detail: 'CtaTemplate lifecycle method',
  },
  {
    label: 'on_start',
    kind: 'function',
    insertText: 'def on_start(self):\n    """Strategy start"""\n    ${1:pass}',
    documentation: 'Called when strategy starts',
    detail: 'CtaTemplate lifecycle method',
  },
  {
    label: 'on_stop',
    kind: 'function',
    insertText: 'def on_stop(self):\n    """Strategy stop"""\n    ${1:pass}',
    documentation: 'Called when strategy stops',
    detail: 'CtaTemplate lifecycle method',
  },
  {
    label: 'on_bar',
    kind: 'function',
    insertText: 'def on_bar(self, bar):\n    """Process bar data"""\n    ${1:pass}',
    documentation: 'Called on each new bar',
    detail: 'CtaTemplate data handler',
  },
  {
    label: 'on_tick',
    kind: 'function',
    insertText: 'def on_tick(self, tick):\n    """Process tick data"""\n    ${1:pass}',
    documentation: 'Called on each new tick',
    detail: 'CtaTemplate data handler',
  },
  {
    label: 'on_trade',
    kind: 'function',
    insertText: 'def on_trade(self, trade):\n    """Process trade update"""\n    ${1:pass}',
    documentation: 'Called when a trade is executed',
    detail: 'CtaTemplate trade handler',
  },
  {
    label: 'on_order',
    kind: 'function',
    insertText: 'def on_order(self, order):\n    """Process order update"""\n    ${1:pass}',
    documentation: 'Called when order status changes',
    detail: 'CtaTemplate order handler',
  },
  // Trading methods
  {
    label: 'buy',
    kind: 'function',
    insertText: 'self.buy(${1:price}, ${2:volume})',
    documentation: 'Open long position',
    detail: 'Trading method',
  },
  {
    label: 'sell',
    kind: 'function',
    insertText: 'self.sell(${1:price}, ${2:volume})',
    documentation: 'Close long position',
    detail: 'Trading method',
  },
  {
    label: 'short',
    kind: 'function',
    insertText: 'self.short(${1:price}, ${2:volume})',
    documentation: 'Open short position',
    detail: 'Trading method',
  },
  {
    label: 'cover',
    kind: 'function',
    insertText: 'self.cover(${1:price}, ${2:volume})',
    documentation: 'Close short position',
    detail: 'Trading method',
  },
  {
    label: 'cancel_all',
    kind: 'function',
    insertText: 'self.cancel_all()',
    documentation: 'Cancel all pending orders',
    detail: 'Trading method',
  },
  // Utility methods
  {
    label: 'write_log',
    kind: 'function',
    insertText: 'self.write_log("${1:message}")',
    documentation: 'Write log message',
    detail: 'Utility method',
  },
  {
    label: 'load_bar',
    kind: 'function',
    insertText: 'self.load_bar(${1:days})',
    documentation: 'Load historical bar data',
    detail: 'Data method',
  },
  {
    label: 'load_tick',
    kind: 'function',
    insertText: 'self.load_tick(${1:days})',
    documentation: 'Load historical tick data',
    detail: 'Data method',
  },
  // Properties
  {
    label: 'pos',
    kind: 'variable',
    insertText: 'self.pos',
    documentation: 'Current position volume',
    detail: 'Strategy property',
  },
  {
    label: 'parameters',
    kind: 'variable',
    insertText: 'parameters = {\n    "${1:param_name}": ${2:default_value},\n}',
    documentation: 'Strategy parameters dictionary',
    detail: 'Strategy configuration',
  },
  // Decorators
  {
    label: '@preserve',
    kind: 'snippet',
    insertText: '@preserve\ndef ${1:method_name}(self):\n    ${2:pass}',
    documentation: 'Mark variable to preserve during hot reload',
    detail: 'Hot reload decorator',
  },
];

const CodeEditor: React.FC<CodeEditorProps> = ({
  initialContent = '',
  language = 'python',
  readOnly = false,
  onChange,
  onSave,
  onCursorChange,
  height = '100%',
  theme = 'vs-dark',
}) => {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const [isEditorReady, setIsEditorReady] = useState(false);

  // Register Python completion provider
  const registerCompletionProvider = useCallback(() => {
    monaco.languages.registerCompletionItemProvider('python', {
      provideCompletionItems: (model, position) => {
        const word = model.getWordUntilPosition(position);
        const range = {
          startLineNumber: position.lineNumber,
          endLineNumber: position.lineNumber,
          startColumn: word.startColumn,
          endColumn: word.endColumn,
        };

        const suggestions: monaco.languages.CompletionItem[] = [];

        // Add Python keywords
        PYTHON_KEYWORDS.forEach(keyword => {
          suggestions.push({
            label: keyword,
            kind: monaco.languages.CompletionItemKind.Keyword,
            insertText: keyword,
            range,
          });
        });

        // Add Strategy API suggestions
        STRATEGY_API_SUGGESTIONS.forEach(suggestion => {
          let kind: monaco.languages.CompletionItemKind;
          switch (suggestion.kind) {
            case 'function':
              kind = monaco.languages.CompletionItemKind.Function;
              break;
            case 'class':
              kind = monaco.languages.CompletionItemKind.Class;
              break;
            case 'variable':
              kind = monaco.languages.CompletionItemKind.Variable;
              break;
            case 'snippet':
              kind = monaco.languages.CompletionItemKind.Snippet;
              break;
            default:
              kind = monaco.languages.CompletionItemKind.Text;
          }

          suggestions.push({
            label: suggestion.label,
            kind,
            insertText: suggestion.insertText,
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: suggestion.documentation,
            detail: suggestion.detail,
            range,
          });
        });

        // Add template snippets
        Object.entries(STRATEGY_TEMPLATE_SNIPPETS).forEach(([name, template]) => {
          suggestions.push({
            label: `snippet:${name}`,
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: template,
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: `Insert ${name} template`,
            detail: 'Strategy template',
            range,
          });
        });

        return { suggestions };
      },
    });
  }, []);

  // Initialize editor
  useEffect(() => {
    if (!containerRef.current) return;

    // Register completion provider before creating editor
    registerCompletionProvider();

    // Create editor instance
    const editor = monaco.editor.create(containerRef.current, {
      value: initialContent,
      language,
      theme,
      readOnly,
      automaticLayout: true,
      minimap: { enabled: true },
      fontSize: 14,
      fontFamily: "'Fira Code', 'Consolas', 'Monaco', monospace",
      lineNumbers: 'on',
      renderLineHighlight: 'all',
      scrollBeyondLastLine: false,
      wordWrap: 'on',
      tabSize: 4,
      insertSpaces: true,
      formatOnPaste: true,
      formatOnType: true,
      suggestOnTriggerCharacters: true,
      quickSuggestions: {
        other: true,
        comments: false,
        strings: false,
      },
      parameterHints: { enabled: true },
      folding: true,
      foldingStrategy: 'indentation',
      showFoldingControls: 'always',
      bracketPairColorization: { enabled: true },
      guides: {
        bracketPairs: true,
        indentation: true,
      },
    });

    editorRef.current = editor;
    setIsEditorReady(true);

    // Content change handler
    editor.onDidChangeModelContent(() => {
      const content = editor.getValue();
      onChange?.(content);
    });

    // Cursor position change handler
    editor.onDidChangeCursorPosition((e) => {
      onCursorChange?.({
        line: e.position.lineNumber,
        column: e.position.column,
      });
    });

    // Save shortcut (Ctrl+S / Cmd+S)
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      const content = editor.getValue();
      onSave?.(content);
    });

    // Cleanup
    return () => {
      editor.dispose();
      editorRef.current = null;
      setIsEditorReady(false);
    };
  }, [language, theme, readOnly, registerCompletionProvider]);

  // Update content when initialContent changes
  useEffect(() => {
    if (editorRef.current && isEditorReady) {
      const currentValue = editorRef.current.getValue();
      if (currentValue !== initialContent) {
        editorRef.current.setValue(initialContent);
      }
    }
  }, [initialContent, isEditorReady]);

  // Update theme
  useEffect(() => {
    if (isEditorReady) {
      monaco.editor.setTheme(theme);
    }
  }, [theme, isEditorReady]);

  // Public methods exposed via ref
  const getValue = useCallback(() => {
    return editorRef.current?.getValue() || '';
  }, []);

  const setValue = useCallback((value: string) => {
    editorRef.current?.setValue(value);
  }, []);

  const focus = useCallback(() => {
    editorRef.current?.focus();
  }, []);

  const insertSnippet = useCallback((snippet: string) => {
    if (editorRef.current) {
      const selection = editorRef.current.getSelection();
      if (selection) {
        editorRef.current.executeEdits('snippet', [{
          range: selection,
          text: snippet,
        }]);
      }
    }
  }, []);

  return (
    <div className="code-editor-container">
      <div className="code-editor-toolbar">
        <span className="editor-language">{language.toUpperCase()}</span>
        <div className="editor-actions">
          <button
            className="editor-action-btn"
            onClick={() => insertSnippet(STRATEGY_TEMPLATE_SNIPPETS.ctaTemplate)}
            title={t('strategyLab.insertTemplate')}
          >
            📄 {t('strategyLab.template')}
          </button>
          <button
            className="editor-action-btn"
            onClick={() => onSave?.(getValue())}
            title={t('strategyLab.save')}
            disabled={readOnly}
          >
            💾 {t('strategyLab.save')}
          </button>
        </div>
      </div>
      <div
        ref={containerRef}
        className="code-editor-monaco"
        style={{ height: typeof height === 'number' ? `${height}px` : height }}
      />
      {!isEditorReady && (
        <div className="code-editor-loading">
          {t('strategyLab.loadingEditor')}
        </div>
      )}
    </div>
  );
};

export default CodeEditor;
