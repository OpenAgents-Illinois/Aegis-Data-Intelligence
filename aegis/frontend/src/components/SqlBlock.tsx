import { useState } from "react";

export default function SqlBlock({ sql }: { sql: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group">
      <pre className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm text-gray-700 overflow-x-auto">
        <code>{sql}</code>
      </pre>
      <button
        onClick={copy}
        className="absolute top-2 right-2 px-2 py-1 text-xs bg-white border border-gray-200 hover:bg-gray-50 text-gray-600 rounded opacity-0 group-hover:opacity-100 transition-opacity shadow-sm"
      >
        {copied ? "Copied!" : "Copy"}
      </button>
    </div>
  );
}
