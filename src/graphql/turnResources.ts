import { gql, type TypedDocumentNode } from '@apollo/client';
import type { ManeuverMove } from '@/components/game/turnResourceChoices';

interface StateResult { state: string; sequenceNumber: number }
export interface BeginManeuverVariables { input: { gameId: string; expectedSequenceNumber: number } }
export interface CompleteManeuverVariables { input: { gameId: string; maneuverId: string; moves: ManeuverMove[]; boostCardId?: string | null } }
export interface DiscardToLimitVariables { input: { gameId: string; pendingId: string; cardIds: string[] } }

// Typed operations live here until the shared generated schema is refreshed.
export const BeginManeuverDocument: TypedDocumentNode<{ beginManeuver: StateResult }, BeginManeuverVariables> = gql`
  mutation BeginManeuver($input: BeginManeuverDto!) {
    beginManeuver(input: $input) { state sequenceNumber phase currentTurnPlayerId turnCount timestamp }
  }
`;
export const CompleteManeuverDocument: TypedDocumentNode<{ maneuver: StateResult }, CompleteManeuverVariables> = gql`
  mutation CompleteManeuver($input: ManeuverDto!) {
    maneuver(input: $input) { state sequenceNumber phase currentTurnPlayerId turnCount timestamp }
  }
`;
export const DiscardToLimitDocument: TypedDocumentNode<{ discardToLimit: StateResult }, DiscardToLimitVariables> = gql`
  mutation DiscardToLimit($input: DiscardToLimitDto!) {
    discardToLimit(input: $input) { state sequenceNumber phase currentTurnPlayerId turnCount timestamp }
  }
`;
