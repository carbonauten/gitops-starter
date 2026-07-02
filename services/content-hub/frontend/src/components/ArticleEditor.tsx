import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";

type ArticleEditorProps = {
  content: string;
  onChange: (html: string) => void;
};

export function ArticleEditor({ content, onChange }: ArticleEditorProps) {
  const { t } = useTranslation();

  const editor = useEditor({
    extensions: [StarterKit],
    content,
    onUpdate: ({ editor: current }) => {
      onChange(current.getHTML());
    },
  });

  useEffect(() => {
    if (editor && content !== editor.getHTML()) {
      editor.commands.setContent(content, false);
    }
  }, [content, editor]);

  if (!editor) {
    return <div className="editor-loading">{t("common.loading")}</div>;
  }

  return (
    <div className="editor-shell">
      <div className="editor-toolbar">
        <button type="button" onClick={() => editor.chain().focus().toggleBold().run()} className={editor.isActive("bold") ? "active" : ""}>
          {t("editor.bold")}
        </button>
        <button type="button" onClick={() => editor.chain().focus().toggleItalic().run()} className={editor.isActive("italic") ? "active" : ""}>
          {t("editor.italic")}
        </button>
        <button type="button" onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} className={editor.isActive("heading", { level: 2 }) ? "active" : ""}>
          {t("editor.heading")}
        </button>
        <button type="button" onClick={() => editor.chain().focus().toggleBulletList().run()} className={editor.isActive("bulletList") ? "active" : ""}>
          {t("editor.bulletList")}
        </button>
        <button type="button" onClick={() => editor.chain().focus().toggleOrderedList().run()} className={editor.isActive("orderedList") ? "active" : ""}>
          {t("editor.orderedList")}
        </button>
      </div>
      <EditorContent editor={editor} className="editor-content" />
    </div>
  );
}
