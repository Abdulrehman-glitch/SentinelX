import { Skeleton } from "boneyard-js/react";

/* ── Shimmer bone primitive ─────────────────────────────────── */
function Bone({ w = "100%", h = 14, r = 6 }: { w?: string | number; h?: number; r?: number }) {
  return (
    <div
      style={{
        width: typeof w === "number" ? `${w}px` : w,
        height: h,
        borderRadius: r,
        background: "var(--sx-skel-bone, #e8eaf0)",
        flexShrink: 0,
      }}
    />
  );
}

/* ── Stat card row skeleton (3 cards) ───────────────────────── */
export function StatCardsSkeleton() {
  return (
    <div className="mb-6 grid gap-3 sm:grid-cols-3">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="flex items-center gap-3 rounded-lg border px-4 py-3"
          style={{ background: "var(--sx-panel)", borderColor: "var(--sx-border)" }}
        >
          <Bone w={8} h={8} r={4} />
          <div className="flex flex-col gap-1.5 flex-1">
            <Bone w="55%" h={10} />
            <Bone w="35%" h={13} />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Table skeleton: header + N data rows ───────────────────── */
export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  const colWidths = ["40%", "25%", "20%", "15%"].slice(0, cols);

  return (
    <div
      className="rounded-xl border overflow-hidden"
      style={{ background: "var(--sx-panel)", borderColor: "var(--sx-border)" }}
    >
      {/* Header row */}
      <div
        className="flex items-center gap-4 px-4 py-3 border-b"
        style={{ borderColor: "var(--sx-border)", background: "var(--sx-bg)" }}
      >
        {colWidths.map((w, i) => (
          <Bone key={i} w={w} h={10} />
        ))}
      </div>

      {/* Data rows */}
      {Array.from({ length: rows }, (_, row) => (
        <div
          key={row}
          className="flex items-center gap-4 px-4 py-3 border-b last:border-b-0"
          style={{ borderColor: "var(--sx-border-md, var(--sx-border))" }}
        >
          {colWidths.map((w, col) => (
            <Bone key={col} w={w} h={12} />
          ))}
        </div>
      ))}
    </div>
  );
}

/* ── Page-level skeleton: stat cards + table ────────────────── */
export function PageSkeleton({ rows = 5, cols = 4, showStats = true }: { rows?: number; cols?: number; showStats?: boolean }) {
  return (
    <>
      {showStats && <StatCardsSkeleton />}
      <TableSkeleton rows={rows} cols={cols} />
    </>
  );
}

/* ── Re-export Skeleton for convenience ─────────────────────── */
export { Skeleton };
