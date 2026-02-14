import { useCallback, useState } from "react";
import { createSnapshot, listSnapshots, restoreSnapshot } from "../api/client";
import { ProjectDSL, SnapshotSummary } from "../types/dsl";

export function useHistory(projectId: string | null, onDslChange: (dsl: ProjectDSL) => void) {
  const [snapshots, setSnapshots] = useState<SnapshotSummary[]>([]);
  const [loadingSnapshots, setLoadingSnapshots] = useState(false);

  const refreshSnapshots = useCallback(async () => {
    if (!projectId) return;
    setLoadingSnapshots(true);
    try {
      const res = await listSnapshots(projectId);
      setSnapshots(res.items);
    } finally {
      setLoadingSnapshots(false);
    }
  }, [projectId]);

  const create = useCallback(async () => {
    if (!projectId) return;
    await createSnapshot(projectId);
    await refreshSnapshots();
  }, [projectId, refreshSnapshots]);

  const restore = useCallback(
    async (snapshotId: string) => {
      if (!projectId) return;
      const res = await restoreSnapshot(projectId, snapshotId);
      onDslChange(res.dsl);
      await refreshSnapshots();
    },
    [onDslChange, projectId, refreshSnapshots]
  );

  return {
    snapshots,
    loadingSnapshots,
    refreshSnapshots,
    create,
    restore,
  };
}
