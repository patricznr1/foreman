// ============================================================
//  FOREMAN Frontend — components/memory/result-cluster.test.tsx
//  Zweck: Verdichtung — bündelt Hinweise einer Maschine; Auflösungs-Bezug graceful
//         (folgt), nicht erfunden.
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { memoryRoleView } from "@/lib/memory/roles";
import { makeNote } from "@/lib/memory/testing/fixtures";
import { assembleSearchResult } from "@/lib/memory/view-model";
import { ResultCluster } from "./result-cluster";

function clusterFixture() {
  const result = assembleSearchResult(
    [makeNote({ id: 1, machine_id: 7 }), makeNote({ id: 2, machine_id: 7 })],
    "x",
  );
  const cluster = result.clusters[0];
  if (!cluster) {
    throw new Error("Fixture lieferte keinen Cluster");
  }
  return { cluster, total: result.total };
}

describe("ResultCluster", () => {
  it("verdichtet mehrere Hinweise einer Maschine zu einer Gruppe", () => {
    const { cluster, total } = clusterFixture();
    render(<ResultCluster cluster={cluster} total={total} roleView={memoryRoleView("technician")} defaultOpen />);
    expect(screen.getByText("2 Hinweise an Maschine 7")).toBeInTheDocument();
  });

  it("markiert den Auflösungs-Bezug graceful (folgt), erfindet ihn nicht", () => {
    const { cluster, total } = clusterFixture();
    render(<ResultCluster cluster={cluster} total={total} roleView={memoryRoleView("technician")} defaultOpen />);
    expect(screen.getByText("gemeinsame Auflösung folgt")).toBeInTheDocument();
  });
});
