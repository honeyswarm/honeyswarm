import { useMemo } from "react";
import CodeMirror, { EditorView, type Extension } from "@uiw/react-codemirror";
import { yaml } from "@codemirror/lang-yaml";
import { StreamLanguage } from "@codemirror/language";
import { properties } from "@codemirror/legacy-modes/mode/properties";
import { oneDark } from "@codemirror/theme-one-dark";

export type CodeLanguage = "yaml" | "ini";

/** Syntax-highlighted code editor (CodeMirror) used for the manifest/config editors. */
export function CodeEditor({
  value,
  onChange,
  language,
  minHeight = "240px",
  readOnly = false,
}: {
  value: string;
  onChange?: (value: string) => void;
  language: CodeLanguage;
  minHeight?: string;
  readOnly?: boolean;
}) {
  const extensions = useMemo<Extension[]>(() => {
    const lang = language === "yaml" ? yaml() : StreamLanguage.define(properties);
    return [lang, EditorView.lineWrapping];
  }, [language]);

  return (
    <CodeMirror
      value={value}
      onChange={onChange}
      theme={oneDark}
      extensions={extensions}
      minHeight={minHeight}
      readOnly={readOnly}
      basicSetup={{
        lineNumbers: true,
        highlightActiveLine: true,
        bracketMatching: true,
        closeBrackets: true,
        autocompletion: false,
      }}
      style={{ border: "1px solid var(--border)", borderRadius: 6, fontSize: 13, overflow: "hidden" }}
    />
  );
}
