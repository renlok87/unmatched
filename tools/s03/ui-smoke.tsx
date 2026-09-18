// Browser-only replay of captured transport fixtures. Production GameView/store;
// API calls are captured and answered from fixtures, not sent to a deployed game.
import React from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import GameView from '../../src/components/game/GameView';
import { useRemoteGameStore } from '../../src/store/remoteGameStore';
import { apolloClient } from '../../src/lib/apolloClient';
import evidence from '../../docs/game-design/evidence/S03/transport-results.json';
import '../../src/App.css';

const calls: unknown[] = [];
const response = (stage: string) => {
  const entry = evidence.http.find(e => e.stage === stage && e.viewer === 'a')!;
  return entry.response.data!;
};
const wire = (stage: string) => JSON.parse(Object.values(response(stage))[0]!.state!);
const load = (stage = 'initial') => {
  const state = wire(stage === 'initial' ? 'begin-draw-only' : stage);
  if (stage === 'initial') {
    state.sequenceNumber = 10;
    state.metadata.actionsRemaining = 2;
    delete state.metadata.pendingManeuver;
    state.handZones.a.cards = [];
  }
  useRemoteGameStore.setState({ currentGameId: state.gameId, localUserId: 'a', lastSequenceNumber: -1,
    connectionStatus: 'connected', connectToGame: async () => {}, actionError: null });
  useRemoteGameStore.getState().applyWireState(state);
};
(apolloClient as any).subscribe = () => ({ subscribe: () => ({ unsubscribe() {} }) });
(apolloClient as any).mutate = async (request: any) => {
  const name = request.mutation.definitions[0].name.value;
  calls.push({ name, variables: request.variables });
  const stage = name === 'BeginManeuver' ? 'begin-draw-only' :
    name === 'DiscardToLimit' ? 'owner-selects-discard' :
    request.variables.input.boostCardId ? 'complete-new-card-boost' : 'complete-draw-only';
  return { data: response(stage) };
};
(window as any).s03 = { calls, load, store: useRemoteGameStore };
(window as any).React = React;
load();
createRoot(document.getElementById('root')!).render(
  <MemoryRouter initialEntries={['/game/s03']}><Routes>
    <Route path="/game/:gameId" element={<GameView />} />
  </Routes></MemoryRouter>,
);
