import random
from modules.cards import create_deck
from modules.evaluator import evaluate_hand
from modules.game_engine import determine_winner

INITIAL_STATE = {
    "player_money": 2000,
    "dealer_money": 2000,
    "ante": 50,
}

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
    game_state["current_bet"] = 0
    game_state["player_phase_bet"] = 0
    game_state["dealer_phase_bet"] = 0


def get_common_response(dealer_action, p_res):
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
    if (
        game_state["player_money"] < game_state["ante"]
        or game_state["dealer_money"] < game_state["ante"]
    ):
        return {"error": "자금이 부족합니다!", "is_game_over": True}

    if game_state["dealer_button"] is None:
        game_state["dealer_button"] = random.choice(["player", "dealer"])

    reset_phase_bets()
    game_state["player_money"] -= game_state["ante"]
    game_state["dealer_money"] -= game_state["ante"]
    game_state["pot"] = game_state["ante"] * 2

    deck = create_deck()
    game_state["deck"] = deck
    game_state["player_hand"] = [deck.pop(), deck.pop()]
    game_state["dealer_hand"] = [deck.pop(), deck.pop()]
    game_state["community_cards"] = []
    game_state["phase"] = "pre-flop"

    dealer_action = None
    if game_state["dealer_button"] == "player":
        d_res = evaluate_hand(game_state["dealer_hand"])
        # 딜러 선공 시 잔액 확인 후 레이즈 결정
        if (d_res.get("score", 0) > 0 or random.random() < 0.3) and game_state[
            "dealer_money"
        ] >= 50:
            dealer_action = "RAISE"
            raise_amount = 50
            game_state["dealer_money"] -= raise_amount
            game_state["pot"] += raise_amount
            game_state["dealer_phase_bet"] = raise_amount
            game_state["current_bet"] = raise_amount
        else:
            dealer_action = "CHECK"

    p_res = evaluate_hand(game_state["player_hand"])
    return get_common_response(dealer_action, p_res)


def next_phase_logic(action, bet):
    curr_phase = game_state["phase"]
    deck = game_state["deck"]

    # 1. 플레이어 베팅 정산 (기존 동일)
    p_needed = game_state["current_bet"] - game_state["player_phase_bet"]
    actual_p_bet = (
        p_needed if action == "call" else (p_needed + bet if action == "raise" else 0)
    )

    if action == "raise":
        game_state["current_bet"] += bet

    if game_state["player_money"] < actual_p_bet:
        return {"error": "자금이 부족합니다!"}

    game_state["player_money"] -= actual_p_bet
    game_state["player_phase_bet"] += actual_p_bet
    game_state["pot"] += actual_p_bet

    # 2. 딜러 반응 및 페이즈 종료 판단
    dealer_msg = ""
    should_proceed = False

    if action == "call":
        should_proceed = True
    elif action == "check":
        if game_state["dealer_button"] == "player":
            should_proceed = True
        else:
            if game_state["dealer_money"] <= 0 or game_state["player_money"] <= 0:
                dealer_msg = ""
                should_proceed = True
            else:
                d_res = evaluate_hand(
                    game_state["dealer_hand"] + game_state["community_cards"]
                )
                can_dealer_raise = (
                    game_state["dealer_money"] >= 50 and game_state["player_money"] > 0
                )
                if can_dealer_raise and (
                    d_res.get("score", 0) > 1 or random.random() < 0.2
                ):
                    r_amt = 50
                    game_state["dealer_money"] -= r_amt
                    game_state["dealer_phase_bet"] = r_amt
                    game_state["current_bet"] = r_amt
                    game_state["pot"] += r_amt
                    dealer_msg = "RAISE"
                    should_proceed = False
                else:
                    dealer_msg = "CHECK"
                    should_proceed = True
    elif action == "raise":
        d_res = evaluate_hand(game_state["dealer_hand"] + game_state["community_cards"])
        if d_res.get("score", 0) == 0 and bet >= 100 and random.random() < 0.6:
            return handle_dealer_fold()

        d_needed = game_state["current_bet"] - game_state["dealer_phase_bet"]
        actual_d_call = min(d_needed, game_state["dealer_money"])
        game_state["dealer_money"] -= actual_d_call
        game_state["dealer_phase_bet"] += actual_d_call
        game_state["pot"] += actual_d_call
        dealer_msg = "CALL"
        should_proceed = True

    # 3. 페이즈 전환 및 새 라운드 선공 결정
    if should_proceed:
        if curr_phase == "river":
            return finish_and_showdown(dealer_msg)

        reset_phase_bets()

        # 카드 오픈
        if curr_phase == "pre-flop":
            game_state["community_cards"] += [deck.pop() for _ in range(3)]
            game_state["phase"] = "flop"
        elif curr_phase in ["flop", "turn"]:
            game_state["community_cards"].append(deck.pop())
            game_state["phase"] = "turn" if curr_phase == "flop" else "river"

        # [핵심] 다음 페이즈 선공 결정
        next_action = ""
        if game_state["dealer_button"] == "player":
            if game_state["dealer_money"] <= 0 or game_state["player_money"] <= 0:
                next_action = ""
            else:
                d_res_new = evaluate_hand(
                    game_state["dealer_hand"] + game_state["community_cards"]
                )
                r_amt = min(50, game_state["dealer_money"])

                if (
                    d_res_new.get("score", 0) > 1 or random.random() < 0.2
                ) and r_amt > 0:
                    # 실제 레이즈 로직 채우기
                    game_state["dealer_money"] -= r_amt
                    game_state["dealer_phase_bet"] = r_amt
                    game_state["current_bet"] = r_amt
                    game_state["pot"] += r_amt
                    next_action = "RAISE"
                else:
                    next_action = "CHECK"

            # dealer_msg 업데이트 (CALL -> CHECK 형태 보장)
            if dealer_msg == "CALL":
                dealer_msg = f"CALL -> {next_action}" if next_action else "CALL"
            else:
                # 유저가 체크해서 넘어온 경우(dealer_msg가 CHECK일 때)도 next_action을 반영
                dealer_msg = next_action if next_action else dealer_msg

    p_final_res = evaluate_hand(
        game_state["player_hand"] + game_state["community_cards"]
    )
    return get_common_response(dealer_msg, p_final_res)


def handle_dealer_fold():
    game_state["player_money"] += game_state["pot"]
    game_state["pot"] = 0
    game_state["phase"] = "waiting"
    game_state["dealer_button"] = "player"
    reset_phase_bets()
    return {
        "phase": "waiting",
        "dealer_action": "FOLD",
        "player_money": game_state["player_money"],
        "dealer_money": game_state["dealer_money"],
        "pot": 0,
        "is_game_over": game_state["dealer_money"] <= 0,
        "dealer_button": "player",
    }


def finish_and_showdown(dealer_action):
    p_final = evaluate_hand(game_state["player_hand"] + game_state["community_cards"])
    d_final = evaluate_hand(game_state["dealer_hand"] + game_state["community_cards"])
    winner = determine_winner(p_final, d_final)
    game_state["phase"] = "showdown"

    if winner == "player":
        game_state["player_money"] += game_state["pot"]
        game_state["dealer_button"] = "player"
    elif winner == "dealer":
        game_state["dealer_money"] += game_state["pot"]
        game_state["dealer_button"] = "dealer"
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
        "dealer_button": game_state["dealer_button"],
        "is_game_over": game_state["player_money"] <= 0
        or game_state["dealer_money"] <= 0,
    }


def fold_game_logic():
    game_state["dealer_money"] += game_state["pot"]
    game_state["pot"] = 0
    game_state["phase"] = "waiting"
    game_state["dealer_button"] = "dealer"
    reset_phase_bets()
    return {
        "phase": "waiting",
        "player_money": game_state["player_money"],
        "dealer_money": game_state["dealer_money"],
        "pot": 0,
        "dealer_button": "dealer",
        "is_game_over": game_state["player_money"] <= 0,
    }


def reset_game_logic():
    game_state["player_money"] = 2000
    game_state["dealer_money"] = 2000
    game_state["pot"] = 0
    game_state["phase"] = "waiting"
    game_state["community_cards"] = []
    game_state["dealer_button"] = None
    reset_phase_bets()
    return {"message": "Game Reset Success"}
