import { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

const api = axios.create({
  baseURL: "http://localhost:8000",
});

// 시간을 멈춰주는 유틸리티 함수
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function App() {
  const [gameData, setGameData] = useState(null);
  const [phase, setPhase] = useState("waiting");
  const [loading, setLoading] = useState(false);
  const [isGameOver, setIsGameOver] = useState(false);
  const [betAmount, setBetAmount] = useState(50);
  const [isBetting, setIsBetting] = useState(false);
  const [dealerMsg, setDealerMsg] = useState("");
  const [isDealerTurn, setIsDealerTurn] = useState(false);
  const [isFolding, setIsFolding] = useState(false);

  const callAmount =
    (gameData?.current_bet || 0) - (gameData?.player_phase_bet || 0);

  useEffect(() => {
    const initGame = async () => {
      try {
        await api.post("/reset");
      } catch (error) {
        console.error("Backend 리셋 실패:", error);
      }
    };
    initGame();
  }, []);

  // 카드 렌더링 로직 (기존과 동일)
  const isCardInBestHand = (card, bestCards) => {
    if (!card || !bestCards) return false;
    return bestCards.some(
      (bc) => bc.rank === card.rank && bc.suit === card.suit,
    );
  };

  const renderCard = (
    card,
    index,
    isCommunity = false,
    isHighlight = false,
  ) => {
    if (!card) return null;
    const isRed = ["♥", "♦"].includes(card.suit);
    let delay = isCommunity ? (index < 3 ? index * 0.1 : 0.05) : index * 0.1;

    return (
      <div
        key={`${card.rank}${card.suit}-${index}`}
        className={`card ${isRed ? "red" : "black"} ${isHighlight ? "highlight" : ""}`}
        style={{ animationDelay: `${delay}s` }}
      >
        <span className="rank">{card.rank}</span>
        <span className="suit">{card.suit}</span>
      </div>
    );
  };

  // --- 핵심 로직 시작 ---

  const handleStartGame = async () => {
    setLoading(true);
    setDealerMsg("");
    setIsFolding(false);

    try {
      const response = await api.get("/start");
      const startData = response.data;
      if (startData.error) {
        alert(startData.error);
        return;
      }

      setGameData(startData);
      setPhase(startData.phase);
      setBetAmount(50);
      setIsBetting(false);

      if (startData.dealer_button === "player") {
        setIsDealerTurn(true);
        await sleep(1500); // 딜러 고민하는 척

        if (startData.dealer_action) {
          setDealerMsg(startData.dealer_action);
          setTimeout(() => setDealerMsg(""), 1500); // 1.5초 후 말풍선 삭제
        }
        setGameData((prev) => ({ ...prev, ...startData }));
      }
    } catch (error) {
      console.error("시작 실패:", error);
    } finally {
      setIsDealerTurn(false);
      setLoading(false);
    }
  };

  const handlePlayerAction = async (actionType) => {
    if (isDealerTurn) return;
    setDealerMsg("");
    setLoading(true);
    setIsDealerTurn(true);

    try {
      const response = await api.get(
        `/next?action=${actionType}&bet=${betAmount}`,
      );
      const newData = response.data;

      if (newData.error) {
        alert(newData.error);
        setIsDealerTurn(false);
        setLoading(false);
        return;
      }

      // 1. 유저 칩 나가는 시간 (600ms)
      await sleep(600);
      setGameData((prev) => ({
        ...prev,
        player_money: newData.player_money,
        dealer_money: newData.dealer_money,
        pot: newData.pot,
        current_bet: newData.current_bet,
        player_phase_bet: newData.player_phase_bet,
      }));

      const isPhaseChanged = newData.phase !== phase;

      if (isPhaseChanged) {
        // 2. 카드 오픈 대기 (1000ms)
        await sleep(1000);
        setPhase(newData.phase);
        setGameData(newData); // 여기서 새로운 카드가 화면에 보임

        // 3. 카드가 다 깔린 후 딜러의 선공 액션 표시 (백엔드에서 보내준 dealer_action)
        if (newData.phase !== "showdown" && newData.dealer_action) {
          await sleep(800); // 딜러가 카드를 보고 고민하는 척
          setDealerMsg(newData.dealer_action); // 이제 무조건 나옵니다!

          if (newData.dealer_action === "CHECK") {
            setTimeout(() => setDealerMsg(""), 2000);
          }
        }
      } else {
        // 페이즈 유지 시 (딜러의 반격)
        setDealerMsg(newData.dealer_action);
        setGameData(newData);
      }
    } catch (error) {
      console.error(error);
    } finally {
      setIsDealerTurn(false);
      setLoading(false);
    }
  };

  const handleFold = async () => {
    if (isDealerTurn) return;
    setIsFolding(true);
    setLoading(true);
    setDealerMsg("");
    try {
      await sleep(600); // 던지는 애니메이션 시간
      const response = await api.post("/fold");
      setGameData(response.data);
      setPhase(response.data.phase);
      setIsBetting(false);
      setIsFolding(false);
      if (response.data.is_game_over)
        setTimeout(() => setIsGameOver(true), 1500);
    } catch (error) {
      console.error("Fold 실패:", error);
      setIsFolding(false);
    } finally {
      setLoading(false);
    }
  };

  const handleFullReset = async () => {
    try {
      await api.post("/reset");
      window.location.reload();
    } catch (error) {
      console.error("리셋 실패:", error);
    }
  };

  return (
    <div className="poker-app">
      <div className="status-bar">
        <div className="money-item dealer">
          Dealer <span>${gameData?.dealer_money ?? 2000}</span>
        </div>
        <div className="money-item pot">
          Pot <span className="pot-text">${gameData?.pot ?? 0}</span>
        </div>
        <div className="money-item player">
          You <span>${gameData?.player_money ?? 2000}</span>
        </div>
      </div>

      <h1>Texas Hold'em Table</h1>

      <div className="game-board">
        <div
          className={`section dealer-section ${phase === "showdown" && gameData?.winner === "dealer" ? "winner-border" : ""}`}
        >
          <h2>Dealer Hand</h2>
          <div className="card-area-wrapper">
            <div className="dealer-action-aside left-aside">
              {gameData?.dealer_button === "dealer" && (
                <span className="d-button-puck">D</span>
              )}
              {dealerMsg && phase !== "showdown" && (
                <div
                  className={`dealer-bubble-side ${dealerMsg.toLowerCase()}`}
                >
                  {dealerMsg}
                </div>
              )}
            </div>
            <div className="card-row">
              {phase === "showdown" && gameData?.dealer_hand ? (
                gameData.dealer_hand.map((card, i) =>
                  renderCard(
                    card,
                    i,
                    false,
                    gameData.winner === "dealer" &&
                      isCardInBestHand(card, gameData.dealer_best_cards),
                  ),
                )
              ) : (
                <>
                  <div className="card-placeholder"></div>
                  <div className="card-placeholder"></div>
                </>
              )}
            </div>
          </div>
          <div className="dealer-status-container">
            <div
              className={`hand-name ${phase === "showdown" ? "active" : ""}`}
            >
              {phase === "showdown" ? gameData?.dealer_best : ""}
            </div>
          </div>
        </div>

        <div className="divider"></div>

        <div className="section community-section">
          <div className="card-row">
            {gameData?.community_cards?.map((card, i) => {
              const isShowdown = phase === "showdown";
              const bestCards = isShowdown
                ? gameData.winner === "dealer"
                  ? gameData.dealer_best_cards
                  : gameData.player_best_cards
                : [];
              return renderCard(
                card,
                i,
                true,
                isShowdown && isCardInBestHand(card, bestCards),
              );
            })}
          </div>
        </div>

        <div className="divider"></div>

        <div
          className={`section player-section ${phase === "showdown" && gameData?.winner === "player" ? "winner-border" : ""}`}
        >
          <h2>Your Hand</h2>
          <div className="card-area-wrapper">
            <div className="dealer-action-aside left-aside">
              {gameData?.dealer_button === "player" && (
                <span className="d-button-puck">D</span>
              )}
            </div>
            <div className={`card-row ${isFolding ? "folding-animation" : ""}`}>
              {gameData?.player_hand?.map((card, i) =>
                renderCard(
                  card,
                  i,
                  false,
                  phase === "showdown" &&
                    gameData.winner === "player" &&
                    isCardInBestHand(card, gameData.player_best_cards),
                ),
              )}
            </div>
          </div>
          <div className={`hand-name ${phase === "showdown" ? "active" : ""}`}>
            {gameData?.player_best}
          </div>
        </div>
      </div>

      {isFolding && (
        <div className="fold-overlay">
          <h2 className="fold-text">FOLD</h2>
        </div>
      )}

      <div className="controls">
        {phase === "waiting" || phase === "showdown" ? (
          <button
            className="btn btn-start luxury"
            onClick={handleStartGame}
            disabled={loading}
          >
            {phase === "showdown" ? "Next Game ($-50)" : "Start Game ($-50)"}
          </button>
        ) : (
          <div className="action-area">
            <div
              className={`action-container ${isDealerTurn ? "disabled-ui" : ""}`}
            >
              {isBetting ? (
                <div className="bet-toggle-container">
                  <div className="bet-slider-box">
                    <div className="bet-label-mini">
                      Raise: <span>${betAmount}</span>
                    </div>
                    <input
                      type="range"
                      min="50"
                      max={Math.min(
                        gameData?.player_money || 2000,
                        gameData?.dealer_money || 2000,
                      )}
                      step="10"
                      value={betAmount}
                      onChange={(e) => setBetAmount(parseInt(e.target.value))}
                    />
                  </div>
                  <div className="bet-toggle-btns">
                    <button
                      className="btn btn-confirm"
                      onClick={() => handlePlayerAction("raise")}
                    >
                      확정
                    </button>
                    <button
                      className="btn btn-cancel"
                      onClick={() => setIsBetting(false)}
                    >
                      취소
                    </button>
                  </div>
                </div>
              ) : (
                <div className="action-group horizontal">
                  <button
                    className="btn btn-fold"
                    onClick={handleFold}
                    disabled={loading}
                  >
                    Fold
                  </button>
                  <button
                    className="btn btn-check"
                    onClick={() => handlePlayerAction("check")}
                    disabled={loading || callAmount > 0}
                  >
                    Check
                  </button>
                  <button
                    className="btn btn-call"
                    onClick={() => handlePlayerAction("call")}
                    disabled={loading || callAmount <= 0}
                  >
                    Call {callAmount > 0 ? `($${callAmount})` : ""}
                  </button>
                  <button
                    className="btn btn-raise"
                    onClick={() => setIsBetting(true)}
                    disabled={loading}
                  >
                    Raise
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {isGameOver && (
        <div className="game-over-overlay">
          <div className="game-over-content">
            <h1 className="luxury-text">
              {gameData?.player_money <= 0 ? "GAME OVER" : "CHAMPION!"}
            </h1>
            <div className="final-stats">
              최종 자산: <span>${gameData?.player_money}</span>
            </div>
            <button className="btn btn-start luxury" onClick={handleFullReset}>
              다시 시작하기
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
