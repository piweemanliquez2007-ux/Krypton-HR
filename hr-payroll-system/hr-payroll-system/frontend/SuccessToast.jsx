import { useEffect, useState } from "react";

export default function SuccessToast({ visible = true, onDismiss, autoDismissMs = 4000 }) {
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    if (visible) {
      setIsMounted(true);
      const timer = setTimeout(() => {
        onDismiss?.();
      }, autoDismissMs);
      return () => clearTimeout(timer);
    }
  }, [visible, onDismiss, autoDismissMs]);

  if (!visible || !isMounted) return null;

  return (
    <div
      className="fixed top-6 right-6 z-[9999] flex flex-col gap-2 pointer-events-none"
      role="alert"
      aria-live="polite"
      aria-atomic="true"
    >
      <div
        className="
          pointer-events-auto
          flex items-center gap-3
          bg-slate-900 border-l-4 border-emerald-500 text-white
          px-5 py-4 rounded-lg shadow-xl shadow-emerald-900/20
          min-w-[320px] max-w-md
          slide-in-right-fade
        "
      >
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-emerald-900/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
          <svg
            className="w-5 h-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-white leading-tight">
            Candidate profile successfully extracted and saved.
          </p>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          className="
            flex-shrink-0 w-8 h-8 rounded-md
            bg-emerald-900/10 hover:bg-emerald-900/20
            border border-emerald-500/20 text-emerald-400 hover:text-white
            transition-colors duration-200
            flex items-center justify-center
          "
          aria-label="Dismiss"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}
