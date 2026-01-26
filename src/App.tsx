import { useEffect } from 'react'
import { useGameStore } from './store/gameStore'
import { BoardView } from './components/board/BoardView'
import { HandView } from './components/cards/HandView'
import { GameControls } from './components/controls/GameControls'
import './App.css'

function App() {
  const { gameState, initializeGame } = useGameStore()

  useEffect(() => {
    // Initialize game on mount
    initializeGame()
  }, [])

  if (!gameState) {
    return (
      <div className="app">
        <div className="loading">
          <h1>Unmatched - Digital Edition</h1>
          <p>Загрузка...</p>
        </div>
      </div>
    )
  }

  const winner = gameState.winner
  const winnerName = winner
    ? gameState.players.find(p => p.id === winner)?.name
    : null

  return (
    <div className="app">
      <header className="app-header">
        <h1>⚔️ Unmatched - Digital Edition</h1>
        {winnerName && (
          <div className="winner-banner">
            🏆 Победитель: {winnerName}!
          </div>
        )}
      </header>

      <main className="game-main">
        <div className="game-layout">
          {/* Left Panel - Player 2 (opponent) */}
          <section className="panel panel-left">
            <div className="panel-header">
              {gameState.players[1]?.name || 'Player 2'}
            </div>
            <div className="opponent-info">
              <div className="opponent-cards">
                Карт в руке: {gameState.players[1]?.hand.length || 0}
              </div>
              <div className="opponent-deck">
                В колоде: {gameState.players[1]?.deck.length || 0}
              </div>
            </div>
            <div className="opponent-fighters">
              {gameState.players[1]?.fighters
                .filter(f => !f.isDefeated)
                .map(f => (
                  <div key={f.id} className="mini-fighter">
                    <span>{f.type === 'hero' ? '🦸' : '🧑‍✈️'}</span>
                    <span>{f.health}/{f.maxHealth}</span>
                  </div>
                ))}
            </div>
          </section>

          {/* Center - Game Board */}
          <section className="panel panel-center">
            <BoardView />
          </section>

          {/* Right Panel - Controls & Current Player */}
          <section className="panel panel-right">
            <GameControls />
            <HandView />
          </section>
        </div>
      </main>

      <footer className="app-footer">
        <div className="footer-info">
          <span>Ход: {gameState.turnCount}</span>
          <span>Фаза: {gameState.phase}</span>
          <span>Игрок: {gameState.players.find(p => p.id === gameState.currentTurn.currentPlayerId)?.name}</span>
        </div>
      </footer>
    </div>
  )
}

export default App
