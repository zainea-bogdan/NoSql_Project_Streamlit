"""Write small fake Wyscout-v3-shaped JSON files to data/fake/ for testing.

    python scripts/make_fake_data.py

Output (3 teams, 60 players, 2 matches, about 400 events per match). Names are invented.
The files use the different shapes the ingest accepts:
    teams.json                  list of objects
    players.json                wrapper {"players": [...]}
    match_<id>.json             one object per file
    events_<id>.json            wrapper {"events": [...], "meta": {...}}
"""
import json
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "fake"
rng = random.Random(2026)
FAKE_IMAGE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"

AREA = {"id": 642, "alpha2code": "RO", "alpha3code": "ROU", "name": "Romania"}
TEAMS = [
    {"wyId": 61001, "name": "Aurora FC", "officialName": "Aurora Football Club", "city": "Valmora"},
    {"wyId": 61002, "name": "Borealis United", "officialName": "Borealis United SC", "city": "Kestrel Bay"},
    {"wyId": 61003, "name": "Cascadia Rovers", "officialName": "Cascadia Rovers FC", "city": "Pinecrest"},
]
for t in TEAMS:
    t.update({"area": AREA, "type": "club", "category": "default", "gender": "male", "imageDataURL": FAKE_IMAGE})

FIRST = ["Tavin", "Corvel", "Mirek", "Lysan", "Oren", "Bastio", "Kael", "Dovan", "Elric", "Fynn", "Garet",
         "Halvar", "Ivo", "Joral", "Kesten", "Lorin", "Marek", "Nilo", "Osric", "Pavel", "Quill", "Rasmo",
         "Sorin", "Teodor", "Ulric", "Valen", "Wendel", "Yorik", "Zeno", "Adrel"]
SYL_A = ["Mor", "Tal", "Ven", "Kas", "Dril", "Ost", "Bel", "Run", "Fen", "Gar", "Lum", "Pra", "Sel", "Vor", "Zan"]
SYL_B = ["ovan", "eski", "ard", "ino", "elli", "mar", "sek", "uro", "ath", "ley", "escu", "anu", "ic", "berg", "ota"]

ROSTER = (  # role code2, position, count
    [("GK", "gk")] * 2
    + [("DF", p) for p in ("cb", "cb", "lb", "rb", "lcb", "rcb", "rb")]
    + [("MD", p) for p in ("dmf", "cmf", "cmf", "amf", "lcmf", "rcmf")]
    + [("FW", p) for p in ("lw", "rw", "cf", "cf", "ss")]
)
ROLE = {
    "GK": {"name": "Goalkeeper", "code2": "GK", "code3": "GKP"},
    "DF": {"name": "Defender", "code2": "DF", "code3": "DEF"},
    "MD": {"name": "Midfielder", "code2": "MD", "code3": "MID"},
    "FW": {"name": "Forward", "code2": "FW", "code3": "FWD"},
}
PASS_WEIGHT = {"GK": 0.25, "DF": 1.4, "MD": 2.2, "FW": 0.7}
FORCED_YOUNG_LEFT = {3, 9, 16}  # roster indexes that always match the R2 shortlist


def clamp(v, lo=0, hi=100):
    return int(max(lo, min(hi, round(v))))


def make_players():
    players, used = [], set()
    for t_idx, team in enumerate(TEAMS):
        for i, (code, position) in enumerate(ROSTER):
            while True:
                first, last = rng.choice(FIRST), rng.choice(SYL_A) + rng.choice(SYL_B)
                if (first, last) not in used:
                    used.add((first, last))
                    break
            young_left = i in FORCED_YOUNG_LEFT
            year = rng.randint(2003, 2006) if young_left else rng.randint(1990, 2007)
            foot = "left" if young_left else rng.choices(["right", "left", "both"], [0.65, 0.25, 0.10])[0]
            national = 7000 + t_idx if young_left or rng.random() < 0.35 else None
            players.append({
                "wyId": 300000 + t_idx * 100 + i,
                "shortName": f"{first[0]}. {last}",
                "firstName": first,
                "middleName": "",
                "lastName": last,
                "height": rng.randint(186, 196) if code == "GK" else rng.randint(168, 192),
                "weight": rng.randint(64, 90),
                "birthDate": f"{year}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                "birthArea": AREA,
                "passportArea": AREA,
                "role": ROLE[code],
                "foot": foot,
                "currentTeamId": team["wyId"],
                "currentNationalTeamId": national,
                "gender": "male",
                "status": "active",
                "imageDataURL": FAKE_IMAGE,
                "_position": position,  # removed before writing
            })
    return players


def lineup(team_players):
    """11 starters (1-4-4-2) + 3 substitutes coming on after minute 60."""
    by_role = {c: [p for p in team_players if p["role"]["code2"] == c] for c in ROLE}
    starters = by_role["GK"][:1] + by_role["DF"][:4] + by_role["MD"][:4] + by_role["FW"][:2]
    subs = [by_role["DF"][4], by_role["MD"][4], by_role["FW"][2]]
    out = {starters[2]["wyId"]: 62, starters[6]["wyId"]: 66, starters[10]["wyId"]: 71}
    entries = [(p, 0, out.get(p["wyId"], 200)) for p in starters]
    entries += [(s, minute, 200) for s, minute in zip(subs, sorted(out.values()))]
    return entries


class MatchSim:
    def __init__(self, match_id, home, away, players):
        self.match_id, self.home, self.away = match_id, home, away
        self.lineups = {t["wyId"]: lineup([p for p in players if p["currentTeamId"] == t["wyId"]]) for t in (home, away)}
        self.events, self.goals = [], {home["wyId"]: [0, 0], away["wyId"]: [0, 0]}  # [1H, total]
        self.next_id = 1_500_000_000 + (match_id % 1000) * 100_000
        self.poss_id = match_id * 1000
        self.big_chance_done = False

    # --------------------------------------------------------- helpers
    def pick(self, team, minute, roles=None, exclude=None):
        cands = [p for p, on, off in self.lineups[team["wyId"]] if on <= minute < off
                 and (roles is None or p["role"]["code2"] in roles) and p is not exclude]
        return rng.choices(cands, [PASS_WEIGHT[p["role"]["code2"]] for p in cands])[0]

    @staticmethod
    def ref(team):
        return {"id": team["wyId"], "name": team["name"], "formation": "4-4-2"}

    def event(self, team, opp, player, t, period, primary, secondary, x, y, poss, **extra):
        self.next_id += 1
        e = {
            "id": self.next_id,
            "matchId": self.match_id,
            "matchPeriod": period,
            "minute": t // 60,
            "second": t % 60,
            "matchTimestamp": f"{t // 3600:02d}:{t // 60 % 60:02d}:{t % 60:02d}.000",
            "type": {"primary": primary, "secondary": list(secondary)},
            "location": {"x": clamp(x), "y": clamp(y)},
            "team": self.ref(team),
            "opponentTeam": self.ref(opp),
            "player": {"id": player["wyId"], "name": player["shortName"], "position": player["_position"]},
            "pass": None, "shot": None, "groundDuel": None, "aerialDuel": None, "infraction": None, "carry": None,
            "possession": poss,
        }
        e.update(extra)
        self.events.append(e)
        return e

    # --------------------------------------------------------- one possession
    def possession(self, T, O, t, period, types, forced_big_chance=False):
        self.poss_id += 1
        poss = {"id": self.poss_id, "duration": "0", "types": list(types), "eventsNumber": 0, "eventIndex": 0,
                "startLocation": None, "endLocation": None, "team": self.ref(T), "attack": None}
        start = len(self.events)
        kind = types[0]
        if forced_big_chance:
            x, y, n_pass = 62, 50, 1
        elif kind == "corner":
            x, y, n_pass = 99, rng.choice([1, 99]), 1
        elif kind == "throw_in":
            x, y, n_pass = rng.randint(20, 80), rng.choice([0, 100]), rng.randint(1, 5)
        elif kind == "free_kick":
            x, y, n_pass = rng.randint(30, 75), rng.randint(15, 85), rng.randint(1, 4)
        elif kind == "goal_kick":
            x, y, n_pass = 6, 50, rng.randint(2, 7)
        elif kind == "counterattack":
            x, y, n_pass = rng.randint(30, 50), rng.randint(20, 80), rng.randint(1, 3)
        else:
            x, y, n_pass = rng.randint(10, 45), rng.randint(10, 90), rng.randint(2, 7)
        first_primary = {"corner": "corner", "free_kick": "free_kick", "throw_in": "throw_in",
                         "goal_kick": "goal_kick"}.get(kind, "pass")

        foul_for_t = False
        last_pass, ended = None, False
        for k in range(n_pass):
            minute = t // 60
            passer = self.pick(T, minute, roles=None if x < 15 else ("DF", "MD", "FW"))
            if k > 0 and not forced_big_chance and rng.random() < 0.12:  # duel pair
                defender = self.pick(O, minute, roles=("DF", "MD"))
                lost = rng.random() < 0.4
                foul = not lost and rng.random() < 0.25
                self.event(T, O, passer, t, period, "duel", ["ground_duel", "offensive_duel"], x, y, poss,
                           groundDuel={"duelType": "offensive_duel", "keptPossession": not lost})
                self.event(O, T, defender, t, period, "duel",
                           ["ground_duel", "defensive_duel"] + (["recovery"] if lost else []), 100 - x, 100 - y, poss,
                           groundDuel={"duelType": "defensive_duel", "recoveredPossession": lost})
                if foul:
                    self.event(O, T, defender, t + 1, period, "infraction", ["foul"], 100 - x, 100 - y, poss,
                               infraction={"type": "regular_foul", "yellowCard": rng.random() < 0.2, "redCard": False})
                    foul_for_t, ended = True, True
                    t += rng.randint(4, 8)
                    break
                t += rng.randint(2, 6)
                if lost:
                    ended = True
                    break
            if forced_big_chance:
                ex, ey, accurate = 86, 46, True
            elif kind == "corner":
                ex, ey, accurate = rng.randint(86, 96), rng.randint(35, 65), rng.random() < 0.55
            else:
                ex, ey = clamp(x + rng.gauss(9, 13)), clamp(y + rng.gauss(0, 16), 2, 98)
                accurate = rng.random() < 0.9 - max(0, ex - x) / 110 - (0.12 if ex > 80 else 0)
            gain = ex - x
            secondary = ["forward_pass" if gain > 5 else "back_pass" if gain < -5 else "lateral_pass"]
            if gain >= 15:
                secondary.append("progressive_pass")
            if x < 66 <= ex:
                secondary.append("pass_to_final_third")
            length = round(math.hypot(gain * 1.05, (ey - y) * 0.68), 1)
            if length > 30:
                secondary.append("long_pass")
            recipient = self.pick(T, minute, roles=("DF", "MD", "FW"), exclude=passer) if accurate else None
            last_pass = self.event(
                T, O, passer, t, period, first_primary if k == 0 else "pass", secondary, x, y, poss,
                **{"pass": {
                    "accurate": accurate, "angle": round(math.degrees(math.atan2(ey - y, gain or 0.1)), 1),
                    "height": "high" if length > 30 else None, "length": length,
                    "recipient": {"id": recipient["wyId"], "name": recipient["shortName"],
                                  "position": recipient["_position"]} if recipient else None,
                    "endLocation": {"x": ex, "y": ey},
                }},
            )
            t += rng.randint(3, 9)
            if not accurate:  # opponent wins the ball
                if rng.random() < 0.6:
                    interceptor = self.pick(O, t // 60, roles=("DF", "MD", "FW"))
                    self.event(O, T, interceptor, t, period, "interception", ["recovery"], 100 - ex, 100 - ey, poss)
                    t += rng.randint(2, 5)
                ended = True
                break
            x, y = ex, ey

        shot_xg, shot_goal, shot_taken = 0.0, False, False
        if not ended:
            minute = t // 60
            if forced_big_chance or (x >= 70 and rng.random() < 0.5):
                last_pass["type"]["secondary"] += ["key_pass", "shot_assist"]
                shooter = self.pick(T, minute, roles=("FW", "MD"))
                sx, sy = (91, 47) if forced_big_chance else (rng.randint(76, 96), rng.randint(30, 70))
                dist = math.hypot((100 - sx) * 1.05, (50 - sy) * 0.68)
                xg = 0.47 if forced_big_chance else round(min(0.75, max(0.02, 0.9 * math.exp(-dist / 7.5))), 3)
                late = minute >= 75
                goal = False if forced_big_chance else rng.random() < min(0.8, xg * (0.6 if late else 1.8))
                on_target = goal or rng.random() < 0.38
                self.event(T, O, shooter, t, period, "shot", ["shot_after_pass"] + (["goal"] if goal else []),
                           sx, sy, poss, shot={
                               "bodyPart": rng.choice(["right_foot", "left_foot", "head_or_other"]),
                               "isGoal": goal, "onTarget": on_target,
                               "goalZone": "gc" if on_target else "obr",
                               "xg": xg, "postShotXg": round(xg * 1.3, 3) if on_target else None,
                               "goalkeeper": None,
                           })
                shot_xg, shot_goal, shot_taken = xg, goal, True
                t += rng.randint(3, 8)
                if goal:
                    self.goals[T["wyId"]][1] += 1
                    if period == "1H":
                        self.goals[T["wyId"]][0] += 1
                elif rng.random() < 0.6:
                    d = self.pick(O, minute, roles=("DF", "GK"))
                    self.event(O, T, d, t, period, "clearance", [], 100 - sx + rng.randint(0, 6), 100 - sy, poss)
                    t += rng.randint(2, 5)
            elif x >= 66:  # attack broken down near the box
                d = self.pick(O, minute, roles=("DF", "MD"))
                cx, cy = 100 - min(x + rng.randint(3, 15), 97), 100 - y
                primary = rng.choice(["clearance", "interception", "duel"])
                secondary = {"clearance": [], "interception": ["recovery"],
                             "duel": ["ground_duel", "defensive_duel", "recovery"]}[primary]
                self.event(O, T, d, t, period, primary, secondary, cx, cy, poss)
                t += rng.randint(2, 5)
            else:  # lost in midfield
                d = self.pick(O, minute, roles=("DF", "MD", "FW"))
                extra = ["counterpressing_recovery"] if rng.random() < 0.2 else []
                self.event(O, T, d, t, period, "interception", ["recovery"] + extra, 100 - x, 100 - y, poss)
                t += rng.randint(2, 5)

        own = [e for e in self.events[start:] if e["team"]["id"] == T["wyId"]]
        poss["eventsNumber"] = len(self.events) - start
        poss["startLocation"] = self.events[start]["location"] if len(self.events) > start else None
        poss["endLocation"] = own[-1]["location"] if own else None
        poss["duration"] = str(max(1, t - (self.events[start]["minute"] * 60 + self.events[start]["second"])))
        max_x = max([e["location"]["x"] for e in own] + [0])
        if shot_taken or max_x >= 60:
            poss["attack"] = {"withShot": shot_taken, "withShotOnGoal": shot_taken and shot_goal,
                              "withGoal": shot_goal, "flank": rng.choice(["left", "center", "right"]), "xg": shot_xg}
        return t, foul_for_t, shot_goal

    # --------------------------------------------------------- full match
    def play(self):
        type_sets = [["attack"], ["counterattack", "attack"], ["corner", "set_piece"], ["throw_in"],
                     ["free_kick", "set_piece"], ["goal_kick"], ["transition_high"], ["transition_low", "attack"]]
        weights = [40, 8, 6, 14, 6, 6, 10, 10]
        for period, t, end, kickoff in (("1H", 1, 47 * 60, self.home), ("2H", 45 * 60 + 1, 95 * 60, self.away)):
            attacking = kickoff
            next_types = None
            while t < end:
                T = attacking
                O = self.away if T is self.home else self.home
                forced = period == "2H" and t >= 79 * 60 and not self.big_chance_done
                types = ["attack"] if forced else next_types or rng.choices(type_sets, weights)[0]
                t, foul_for_t, goal = self.possession(T, O, t, period, types, forced_big_chance=forced)
                if forced:
                    self.big_chance_done = True
                next_types = ["free_kick", "set_piece"] if foul_for_t else None
                attacking = T if foul_for_t else O
                t += rng.randint(20, 45) if not goal else 60
        return self.events

    def match_doc(self):
        h, a = self.home, self.away
        hg, ag = self.goals[h["wyId"]], self.goals[a["wyId"]]
        winner = h["wyId"] if hg[1] > ag[1] else a["wyId"] if ag[1] > hg[1] else 0
        day = 8 if self.match_id % 2 else 15
        return {
            "wyId": self.match_id,
            "label": f"{h['name']} - {a['name']}, {hg[1]}-{ag[1]}",
            "date": f"November {day}, 2026 at 6:00:00 PM GMT+2",
            "dateutc": f"2026-11-{day:02d} 16:00:00",
            "status": "Played",
            "duration": "Regular",
            "winner": winner,
            "competitionId": 99001,
            "seasonId": 199001,
            "roundId": 299001,
            "gameweek": 12 + (self.match_id % 2),
            "venue": f"{h['city']} Arena",
            "teamsData": {
                str(h["wyId"]): {"teamId": h["wyId"], "side": "home", "score": hg[1], "scoreHT": hg[0], "coachId": 0},
                str(a["wyId"]): {"teamId": a["wyId"], "side": "away", "score": ag[1], "scoreHT": ag[0], "coachId": 0},
            },
        }


def write(name, data):
    path = OUT / name
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    players = make_players()
    fixtures = [(5900001, TEAMS[0], TEAMS[1]), (5900002, TEAMS[2], TEAMS[0])]
    written = [write("teams.json", TEAMS)]
    for match_id, home, away in fixtures:
        sim = MatchSim(match_id, home, away, players)
        events = sim.play()
        written.append(write(f"match_{match_id}.json", sim.match_doc()))
        written.append(write(f"events_{match_id}.json", {"events": events, "meta": {"source": "fake"}}))
        shots = [e for e in events if e["type"]["primary"] == "shot"]
        print(f"match {match_id}: {sim.match_doc()['label']}, {len(events)} events, {len(shots)} shots")
    for p in players:
        p.pop("_position")
    written.insert(1, write("players.json", {"players": players}))
    print("\nWrote:")
    for path in written:
        print(f"  {path}")
    print("\nIngest order in the app: teams.json -> players.json -> match_*.json -> events_*.json")


if __name__ == "__main__":
    main()
