import { useEffect, useState } from "react";

import robotIcon from "./assets/robot-icon.png";
import { ProviderCard } from "./components/ProviderCard";
import type { UsageCollection } from "./lib/types";

const emptyCollection: UsageCollection = {
  items: [],
  updatedAt: "",
  isDemoMode: false,
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:6736";

async function refreshUsage() {
  const response = await fetch(`${apiBaseUrl}/api/v1/refresh`, { method: "POST" });
  if (!response.ok) {
    throw new Error("refresh request failed");
  }
}

async function fetchUsage() {
  const response = await fetch(`${apiBaseUrl}/api/v1/usage`);
  if (!response.ok) {
    throw new Error("usage request failed");
  }
  return (await response.json()) as UsageCollection;
}

export default function App() {
  const [collection, setCollection] = useState<UsageCollection>(emptyCollection);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const load = async () => {
      try {
        await refreshUsage();
        const data = await fetchUsage();
        if (!active) return;
        setCollection(data);
        setError(null);
      } catch {
        if (!active) return;
        setError("백엔드 응답을 가져오지 못했습니다.");
      } finally {
        if (active) setLoading(false);
      }
    };

    void load();
    const timer = window.setInterval(load, 5000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="min-h-screen p-3.5 md:p-4">
      <div className="mx-auto grid max-w-7xl gap-4">
        <header className="panel-box px-4 py-4 md:px-5">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-7">
              <span className="grid h-16 w-16 place-items-center rounded-2xl border-2 border-ink bg-paper p-1.5">
                <img alt="Robot icon" className="h-11 w-11 object-contain" src={robotIcon} />
              </span>
              <h1 className="font-['Archivo_Black','IBM_Plex_Sans_KR',sans-serif] text-[clamp(2rem,4vw,3.35rem)] leading-[0.94]">
                AI Tool Dashboard
              </h1>
            </div>

            <div className="flex flex-wrap gap-2">
              <span className="rounded-full border-2 border-ink bg-blue-accent px-2.5 py-1 text-[0.77rem] font-extrabold">
                {collection.items.length} Tools
              </span>
            </div>
          </div>

          {error ? (
            <div className="mt-4 rounded-[18px] border-[3px] border-ink bg-yellow-accent px-4 py-3 text-sm font-semibold">
              {error}
            </div>
          ) : null}
        </header>

        <div className="mb-10 mt-2 flex justify-end gap-2">
          <button
            className="inline-flex items-center justify-center rounded-[14px] border-[3px] border-ink bg-action-add px-4 py-2 text-[0.82rem] font-black leading-none shadow-[0_3px_0_0_var(--color-ink)]"
            type="button"
          >
            추가
          </button>
          <button
            className="inline-flex items-center justify-center rounded-[14px] border-[3px] border-ink bg-action-edit px-4 py-2 text-[0.82rem] font-black leading-none shadow-[0_3px_0_0_var(--color-ink)]"
            type="button"
          >
            수정
          </button>
          <button
            className="inline-flex items-center justify-center rounded-[14px] border-[3px] border-ink bg-action-remove px-4 py-2 text-[0.82rem] font-black leading-none shadow-[0_3px_0_0_var(--color-ink)]"
            type="button"
          >
            제거
          </button>
        </div>

        <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {loading
            ? collection.items.map((snapshot) => (
                <ProviderCard key={snapshot.providerId} snapshot={snapshot} />
              ))
            : collection.items.map((snapshot) => (
                <ProviderCard key={snapshot.providerId} snapshot={snapshot} />
              ))}
        </section>
      </div>
    </div>
  );
}
