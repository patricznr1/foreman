// ============================================================
//  FOREMAN Frontend — lib/state/use-topic.ts
//  Zweck: React-Hooks auf die abgeleitete State-Ebene. Komponenten lesen NUR
//         hierüber (nie den Transport). useTopicState liefert die fünf
//         Pflichtzustände als DataState<T>; useConnectionStatus den
//         Verbindungsstatus für die globale Live-/Degradations-Anzeige.
//  Architektur-Einordnung: State-Ebene 2 ↔ React (useSyncExternalStore).
// ============================================================
"use client";

import { useCallback } from "react";
import { useSyncExternalStore } from "react";
import type { RealtimeStore, TopicView } from "../realtime/realtime-store";
import type { ConnectionStatus } from "../realtime/transport";
import { type DataState, type DeriveOptions, deriveDataState } from "./view-state";

export function useConnectionStatus(store: RealtimeStore): ConnectionStatus {
  return useSyncExternalStore(
    (callback) => store.subscribeStatus(() => callback()),
    () => store.getStatus(),
    () => "closed" as ConnectionStatus,
  );
}

export function useTopicView(store: RealtimeStore, topic: string): TopicView {
  const subscribe = useCallback(
    (callback: () => void) => store.subscribeTopic(topic, callback),
    [store, topic],
  );
  const getSnapshot = useCallback(() => store.getTopicView(topic), [store, topic]);
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

export function useTopicState<T>(
  store: RealtimeStore,
  topic: string,
  options?: DeriveOptions<T>,
): DataState<T> {
  const topicView = useTopicView(store, topic);
  const status = useConnectionStatus(store);
  return deriveDataState<T>(topicView, status, options);
}
