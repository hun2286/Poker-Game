import random
from modules.cards import create_deck
from modules.evaluator import evaluate_hand
from modules.game_engine import determine_winner

# 초기 게임 설정값
INITIAL_STATE = {
    "player_money": 2000,
    "dealer_money": 2000,
    "ante": 50,
}

# 실시간 게임 상태 관리 객체
game_state = {
    "deck": [],
    "player_hand": [],
    "dealer_hand": [],
    "community_cards": [],
    "phase": "waiting",
    "pot": 0,
    "dealer_button": None,
    "current_bet": 0,
    "player_phase_bet": 0,
    "dealer_phase_bet": 0,
    **INITIAL_STATE,
}


def reset_phase_bets():
    """각 페이즈(Flop, Turn 등)가 시작될 때 베팅 기록 초기화"""
    game_state["current_bet"] = 0
    game_state["player_phase_bet"] = 0
    game_state["dealer_phase_bet"] = 0


def decide_dealer_action(current_cards):
    """
    딜러의 패 강도에 따른 확률적 의사결정 함수
    - 트리플 이상(score >= 3): 80% 확률로 RAISE
    - 투페어/원페어(score >= 1): 40% 확률로 RAISE
    - 하이카드: 15% 확률로 블러핑 RAISE
    """
    res = evaluate_hand(current_cards)
    score = res.get("score", 0)

    if score >= 3:
        return "RAISE" if random.random() < 0.8 else "CHECK"
    if score >= 1:
        return "RAISE" if random.random() < 0.4 else "CHECK"
    return "RAISE" if random.random() < 0.15 else "CHECK"


def get_common_response(dealer_action, p_res):
    """프론트엔드로 전달할 공통 응답 객체 생성"""
    return {
        "phase": game_state["phase"],
        "dealer_action": dealer_action,
        "community_cards": game_state["community_cards"],
        "player_hand": game_state["player_hand"],
        "player_best": p_res["name"],
        "player_money": game_state["player_money"],
        "dealer_money": game_state["dealer_money"],
        "pot": game_state["pot"],
        "dealer_button": game_state["dealer_button"],
        "current_bet": game_state["current_bet"],
        "player_phase_bet": game_state["player_phase_bet"],
    }


def start_game_logic():
    """새로운 게임 라운드 시작"""
    if (
        game_state["player_money"] < game_state["ante"]
        or game_state["dealer_money"] < game_state["ante"]
    ):
        return {"error": "자금이 부족합니다!", "is_game_over": True}

    # 🔄 버튼 로테이션 (승패 무관 토글)
    if game_state["dealer_button"] is None:
        game_state["dealer_button"] = random.choice(["player", "dealer"])
    else:
        game_state["dealer_button"] = (
            "player" if game_state["dealer_button"] == "dealer" else "dealer"
        )

    reset_phase_bets()

    # 안티(Ante) 지불 및 초기 베팅액 설정
    game_state["player_money"] -= game_state["ante"]
    game_state["dealer_money"] -= game_state["ante"]
    game_state["pot"] = game_state["ante"] * 2

    # 🔴 중요: 프리플랍 시작 시 안티를 '현재 페이즈 베팅액'으로 간주
    game_state["player_phase_bet"] = game_state["ante"]
    game_state["dealer_phase_bet"] = game_state["ante"]
    game_state["current_bet"] = game_state["ante"]

    deck = create_deck()
    game_state["deck"] = deck
    game_state["player_hand"] = [deck.pop(), deck.pop()]
    game_state["dealer_hand"] = [deck.pop(), deck.pop()]
    game_state["community_cards"] = []
    game_state["phase"] = "pre-flop"

    dealer_action = ""
    # 딜러 선공일 경우 (유저가 D버튼)
    if game_state["dealer_button"] == "player":
        dealer_action = decide_dealer_action(game_state["dealer_hand"])
        if dealer_action == "RAISE" and game_state["dealer_money"] >= 50:
            raise_amount = 50
            game_state["dealer_money"] -= raise_amount
            game_state["pot"] += raise_amount
            # 🔴 안티(50) + 레이즈(50) = 총 100 베팅으로 업데이트
            game_state["dealer_phase_bet"] = game_state["ante"] + raise_amount
            game_state["current_bet"] = game_state["ante"] + raise_amount
        else:
            dealer_action = "CHECK"

    p_res = evaluate_hand(game_state["player_hand"])
    return get_common_response(dealer_action, p_res)


def next_phase_logic(action, bet):
    """플레이어 액션에 따른 게임 진행 및 페이즈 전환 로직 보정"""
    curr_phase = game_state["phase"]
    deck = game_state["deck"]

    # 1. 플레이어 베팅 처리
    p_needed = game_state["current_bet"] - game_state["player_phase_bet"]
    actual_p_bet = 0

    if action == "call":
        actual_p_bet = p_needed
    elif action == "raise":
        actual_p_bet = p_needed + bet
        game_state["current_bet"] += bet
    elif action == "check":
        if p_needed > 0:
            return {
                "error": "베팅 금액이 있어 체크할 수 없습니다. 콜이나 폴드를 하세요."
            }
        actual_p_bet = 0

    if game_state["player_money"] < actual_p_bet:
        return {"error": "자금이 부족합니다!"}

    game_state["player_money"] -= actual_p_bet
    game_state["player_phase_bet"] += actual_p_bet
    game_state["pot"] += actual_p_bet

    # 2. 딜러 반응 결정 (Action Closing Logic)
    dealer_msg = ""
    should_proceed = False

    # 상황 A: 유저가 CALL함 -> 베팅 금액이 일치해짐 -> 페이즈 종료
    if action == "call":
        dealer_msg = "CALL"
        should_proceed = True

    # 상황 B: 유저가 CHECK함
    elif action == "check":
        # 유저가 D버튼(dealer_button == "player")을 가졌다면 유저는 '후공'입니다.
        # 즉, 딜러가 이미 선공으로 액션을 마쳤으므로 유저가 체크하면 즉시 페이즈가 끝나야 합니다.
        if game_state["dealer_button"] == "player":
            should_proceed = True
            dealer_msg = "CHECK"  # 딜러의 이전 액션을 확인하는 용도

        # 유저가 D버튼이 없다면 유저가 '선공'입니다.
        # 유저가 먼저 체크했으니, 이제 후공인 딜러에게 기회를 줍니다.
        else:
            dealer_msg = decide_dealer_action(
                game_state["dealer_hand"] + game_state["community_cards"]
            )
            if dealer_msg == "RAISE":
                r_amt = 50
                game_state["dealer_money"] -= r_amt
                game_state["dealer_phase_bet"] += r_amt
                game_state["current_bet"] += r_amt
                game_state["pot"] += r_amt
                should_proceed = False  # 딜러가 판을 키웠으니 유저가 다시 반응해야 함
            else:
                dealer_msg = "CHECK"
                should_proceed = True  # 둘 다 체크했으니 페이즈 종료

    # 상황 C: 유저가 RAISE함
    elif action == "raise":
        d_res = evaluate_hand(game_state["dealer_hand"] + game_state["community_cards"])
        # 폴드 로직
        if d_res.get("score", 0) == 0 and bet >= 100 and random.random() < 0.6:
            return handle_dealer_fold()

        # 딜러는 일단 따라가는(CALL) 것으로 처리 (더 고도화하면 여기서 딜러가 리레이즈 가능)
        d_needed = game_state["current_bet"] - game_state["dealer_phase_bet"]
        actual_d_call = min(d_needed, game_state["dealer_money"])
        game_state["dealer_money"] -= actual_d_call
        game_state["dealer_phase_bet"] += actual_d_call
        game_state["pot"] += actual_d_call
        dealer_msg = "CALL"
        should_proceed = True  # 유저 레이즈에 딜러가 콜했으니 금액이 같아져서 종료

    # 3. 페이즈 전환 (금액이 일치할 때만 실행)
    if should_proceed:
        # 🔴 [추가] 올인 상황 체크: 한 명이라도 잔액이 0원이고 베팅액이 맞춰졌다면
        is_all_in = game_state["player_money"] == 0 or game_state["dealer_money"] == 0

        # 🔴 리버가 끝났거나, 올인 상황이라면 즉시 쇼다운으로 점프
        if curr_phase == "river" or is_all_in:
            # 올인 시 아직 안 깔린 커뮤니티 카드가 있다면 모두 뽑기
            remaining = 5 - len(game_state["community_cards"])
            if remaining > 0:
                game_state["community_cards"] += [deck.pop() for _ in range(remaining)]

            # 바로 결과 정산 함수 호출
            return finish_and_showdown(dealer_msg)

        # 일반적인 페이즈 전환 (올인이 아닐 때만 실행)
        reset_phase_bets()

        if curr_phase == "pre-flop":
            game_state["community_cards"] += [deck.pop() for _ in range(3)]
            game_state["phase"] = "flop"
        elif curr_phase in ["flop", "turn"]:
            game_state["community_cards"].append(deck.pop())
            game_state["phase"] = "turn" if curr_phase == "flop" else "river"

        # 다음 페이즈 선공 결정 (딜러 버튼 위치에 따라)
        if game_state["dealer_button"] == "player":
            next_action = decide_dealer_action(
                game_state["dealer_hand"] + game_state["community_cards"]
            )
            if next_action == "RAISE":
                r_amt = min(50, game_state["dealer_money"])
                game_state["dealer_money"] -= r_amt
                game_state["dealer_phase_bet"] = r_amt
                game_state["current_bet"] = r_amt
                game_state["pot"] += r_amt
            else:
                next_action = "CHECK"
            dealer_msg = f"{dealer_msg} -> {next_action}" if dealer_msg else next_action

    p_final_res = evaluate_hand(
        game_state["player_hand"] + game_state["community_cards"]
    )
    return get_common_response(dealer_msg, p_final_res)


def handle_dealer_fold():
    """딜러가 기권했을 때 정산 로직"""
    game_state["player_money"] += game_state["pot"]
    game_state["pot"] = 0
    game_state["phase"] = "waiting"
    reset_phase_bets()
    return {
        "phase": "waiting",
        "dealer_action": "FOLD",
        "player_money": game_state["player_money"],
        "dealer_money": game_state["dealer_money"],
        "pot": 0,
        "is_game_over": game_state["dealer_money"] <= 0,
    }


def finish_and_showdown(dealer_action):
    """리버 종료 후 승자 판정 및 칩 정산"""
    p_final = evaluate_hand(game_state["player_hand"] + game_state["community_cards"])
    d_final = evaluate_hand(game_state["dealer_hand"] + game_state["community_cards"])
    winner = determine_winner(p_final, d_final)
    game_state["phase"] = "showdown"

    if winner == "player":
        game_state["player_money"] += game_state["pot"]
    elif winner == "dealer":
        game_state["dealer_money"] += game_state["pot"]
    elif winner == "draw":
        game_state["player_money"] += game_state["pot"] // 2
        game_state["dealer_money"] += game_state["pot"] // 2

    current_pot = game_state["pot"]
    game_state["pot"] = 0
    reset_phase_bets()

    return {
        "phase": "showdown",
        "dealer_action": dealer_action,
        "community_cards": game_state["community_cards"],
        "player_hand": game_state["player_hand"],
        "dealer_hand": game_state["dealer_hand"],
        "winner": winner,
        "player_best": p_final["name"],
        "dealer_best": d_final["name"],
        "player_best_cards": p_final["cards"],
        "dealer_best_cards": d_final["cards"],
        "player_money": game_state["player_money"],
        "dealer_money": game_state["dealer_money"],
        "pot": current_pot,
        "is_game_over": game_state["player_money"] <= 0
        or game_state["dealer_money"] <= 0,
    }


def fold_game_logic():
    """플레이어가 기권했을 때 정산 로직"""
    game_state["dealer_money"] += game_state["pot"]
    game_state["pot"] = 0
    game_state["phase"] = "waiting"
    reset_phase_bets()
    return {
        "phase": "waiting",
        "player_money": game_state["player_money"],
        "dealer_money": game_state["dealer_money"],
        "pot": 0,
        "is_game_over": game_state["player_money"] <= 0,
    }


def reset_game_logic():
    """게임을 초기 자본금 상태로 리셋"""
    global game_state
    game_state.update(
        {
            "player_money": 2000,
            "dealer_money": 2000,
            "pot": 0,
            "phase": "waiting",
            "community_cards": [],
            "dealer_button": None,
        }
    )
    reset_phase_bets()
    return {"message": "Game Reset Success"}
