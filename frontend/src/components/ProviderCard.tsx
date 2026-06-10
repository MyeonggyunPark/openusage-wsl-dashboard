import type { Metric, Snapshot } from "../lib/types";
import { providerIcons } from "../lib/provider-icons";

function getDisplayRatio(metric: Metric) {
  if (metric.used == null || metric.limit == null || metric.limit === 0) {
    return 0;
  }

  return Math.max(0, Math.min(1, metric.used / metric.limit));
}

function getGaugeColor(ratio: number) {
  const percentage = ratio * 100;
  if (percentage >= 90) return "var(--color-gauge-low)";
  if (percentage >= 70) return "var(--color-gauge-mid)";
  if (percentage >= 15) return "var(--color-gauge-high)";
  return "var(--color-gauge-full)";
}

function getMetricGaugeColor(metric: Metric, ratio: number) {
  if (metric.used == null || metric.limit == null || metric.limit === 0) {
    return getGaugeColor(0);
  }

  const usedRatio = Math.max(0, Math.min(1, metric.used / metric.limit));
  return getGaugeColor(usedRatio);
}

function isLocalSessionUsageMetric(metric: Metric) {
  return metric.meta?.source === "local_session" && (metric.label === "5h" || metric.label === "7d");
}

function renderMetricValue(metric: Metric) {
  if (metric.type === "badge") return metric.text;
  if (metric.type === "text") {
    if (metric.value === "Included") {
      return "포함";
    }
    return metric.value;
  }
  if (metric.used == null || metric.limit == null) return "--";
  if (metric.unit === "percent") return `${Math.round(getDisplayRatio(metric) * 100)}%`;
  if (metric.unit === "count") return `${Math.round(getDisplayRatio(metric) * 100)}%`;
  return `${metric.used} / ${metric.limit}`;
}

function renderMetricLabel(metric: Metric) {
  let baseLabel = metric.label;
  if (metric.label === "5h") {
    baseLabel = "5시간 사용량";
  } else if (metric.label === "7d") {
    baseLabel = "7일 사용량";
  } else if (metric.label === "Context Usage") {
    baseLabel = "컨텍스트 사용량";
  } else if (metric.label === "Inline Suggestions") {
    baseLabel = "인라인 제안";
  } else if (metric.label === "Chat messages") {
    baseLabel = "채팅 메시지";
  } else if (metric.label === "Premium requests") {
    baseLabel = "프리미엄 요청";
  }

  if (!metric.resetsAt) {
    return baseLabel;
  }

  const resetAt = new Date(metric.resetsAt);
  if (Number.isNaN(resetAt.getTime())) {
    return baseLabel;
  }

  if (metric.label === "5h") {
    return `${baseLabel} (${resetAt.toLocaleTimeString("ko-KR", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    })})`;
  }

  if (metric.label === "7d") {
    return `${baseLabel} (${resetAt.getMonth() + 1}월 ${resetAt.getDate()}일 ${resetAt.toLocaleTimeString("ko-KR", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    })})`;
  }

  return baseLabel;
}

function ProgressLine({ metric }: { metric: Metric }) {
  const ratio = metric.type === "progress" ? getDisplayRatio(metric) : 0;
  const gaugeColor = getMetricGaugeColor(metric, ratio);
  const isIncludedMetric = metric.type === "text" && metric.value === "Included";
  const isTextUsageMetric = metric.type === "text" && isLocalSessionUsageMetric(metric);

  return (
    <div className="grid gap-2.5">
      <div className="flex items-center justify-between gap-3">
        <span>{renderMetricLabel(metric)}</span>
        <strong>{renderMetricValue(metric)}</strong>
      </div>
      {metric.type === "progress" ? (
        <div className="h-4 overflow-hidden rounded-full border-[3px] border-ink bg-gauge-track">
          <div
            className="h-full"
            style={{
              width: `${ratio * 100}%`,
              background: gaugeColor,
            }}
          />
        </div>
      ) : isIncludedMetric || isTextUsageMetric ? (
        <div className="h-4 overflow-hidden rounded-full border-[3px] border-ink bg-gauge-track">
          <div
            className="h-full"
            style={{
              width: isIncludedMetric ? "100%" : "0%",
              background: "var(--color-gauge-included)",
            }}
          />
        </div>
      ) : (
        <div
          className="rounded-2xl border-2 bg-gauge-track px-3 py-2 font-bold"
          style={{ borderColor: metric.color ?? gaugeColor }}
        >
          {renderMetricValue(metric)}
        </div>
      )}
    </div>
  );
}

function orderMetrics(snapshot: Snapshot) {
  if (snapshot.providerId !== "copilot") {
    return snapshot.metrics;
  }

  const priority = new Map([
    ["Premium requests", 0],
    ["Inline Suggestions", 1],
    ["Chat messages", 2],
  ]);

  return [...snapshot.metrics].sort((left, right) => {
    const leftRank = priority.get(left.label) ?? 99;
    const rightRank = priority.get(right.label) ?? 99;
    return leftRank - rightRank;
  });
}

function MetricList({ snapshot }: { snapshot: Snapshot }) {
  const metrics = orderMetrics(snapshot).slice(0, 3);

  return (
    <div className="grid gap-6">
      {metrics.map((metric) => (
        <ProgressLine key={`${snapshot.providerId}-${metric.label}`} metric={metric} />
      ))}
    </div>
  );
}

function statusClass(status: Snapshot["status"]) {
  if (status === "auth_missing" || status === "auth_expired") {
    return "bg-[var(--color-yellow-accent)]";
  }
  return "bg-[var(--color-salmon-accent)]";
}

function statusLabel(status: Snapshot["status"]) {
  if (status === "auth_missing") return "인증 필요";
  if (status === "auth_expired") return "재인증 필요";
  if (status === "network_error") return "네트워크 오류";
  if (status === "provider_error") return "공급자 오류";
  if (status === "parse_error") return "파싱 오류";
  return null;
}

export function ProviderCard({ snapshot }: { snapshot: Snapshot }) {
  const primaryMetrics = orderMetrics(snapshot).slice(0, 3);
  const issueLabel = statusLabel(snapshot.status);
  const primaryWarning = snapshot.warnings[0];

  return (
    <article className="panel-box flex h-full flex-col p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-4">
          <span
            className={`grid h-12 w-12 place-items-center rounded-[14px] border-2 border-ink bg-paper ${
              snapshot.providerId === "copilot" ? "p-1" : "p-2"
            }`}
          >
            <img
              alt={`${snapshot.displayName} icon`}
              className={snapshot.providerId === "copilot" ? "h-10 w-10 object-contain" : "h-7 w-7 object-contain"}
              src={providerIcons[snapshot.providerId] ?? providerIcons.codex}
            />
          </span>
          <h3 className="text-2xl font-black tracking-[0.04em]">{snapshot.displayName}</h3>
        </div>
        <div className="flex items-center gap-2 self-center">
          <span className="inline-flex items-center justify-center rounded-xl border-2 border-ink bg-paper px-3 py-1.5 text-[0.82rem] font-black capitalize leading-none">
            {snapshot.plan}
          </span>
          {issueLabel ? (
            <span
              className={`rounded-full border-2 border-ink px-2.5 py-1 text-[0.77rem] font-extrabold ${statusClass(
                snapshot.status,
              )}`}
            >
              {issueLabel}
            </span>
          ) : null}
        </div>
      </div>

      <div className="my-6 flex-1">
        {primaryMetrics.length > 0 ? (
          <MetricList snapshot={snapshot} />
        ) : (
          <div className="grid gap-3">
            <div className="rounded-[18px] border-[3px] border-ink bg-gauge-track px-4 py-4">
              <p className="text-sm font-black">
                {issueLabel ? `${issueLabel}: ` : ""}
                {primaryWarning ?? "표시할 사용량 데이터가 아직 없습니다."}
              </p>
            </div>
            <div className="grid gap-2 text-sm font-semibold text-gray-600">
              <div className="flex items-center justify-between rounded-[14px] border-2 border-dashed border-ink px-3 py-2">
                <span>상태</span>
                <strong>{snapshot.sourceState}</strong>
              </div>
              <div className="flex items-center justify-between rounded-[14px] border-2 border-dashed border-ink px-3 py-2">
                <span>플랜</span>
                <strong className="capitalize">{snapshot.plan}</strong>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="mt-4 flex justify-end text-sm text-gray-500">
        <strong>Last Update - {new Date(snapshot.fetchedAt).toLocaleTimeString("ko-KR")}</strong>
      </div>
    </article>
  );
}
