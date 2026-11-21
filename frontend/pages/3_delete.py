import streamlit as st

import api
import viz

st.title("Delete documents")
st.caption("Events are never deleted: they are the match history. Deleting a team can optionally "
           "delete its players too (cascade).")

mode = st.radio("Collection", ["Players", "Teams"], horizontal=True, key="del_mode")
nonce = st.session_state.setdefault("del_nonce", 0)  # new table after each delete, so no stale ticks

try:
    teams = api.teams()
    team_id = None
    if mode == "Players":
        team_names = {t["id"]: f"{t['name']} ({t['id']})" for t in teams}
        team_id = st.selectbox("Team", [None] + list(team_names),
                               format_func=lambda i: "All teams" if i is None else team_names[i], key="del_team")
        rows = api.players(team_id)
    else:
        rows = teams
except api.ApiError as exc:
    st.error(str(exc))
    st.stop()

if not rows:
    st.info("No documents.")
else:
    selected = viz.selection_table(rows, key=f"del_table_{mode}_{team_id}_{nonce}")
    names = {r["id"]: r.get("shortName") or r.get("name") or r["id"] for r in rows}

    if selected:
        st.subheader("Impact")
        impact_fn = api.player_impact if mode == "Players" else api.team_impact
        impacts = []
        for doc_id in selected:
            try:
                imp = impact_fn(doc_id)
            except api.ApiError as exc:
                st.error(str(exc))
                continue
            entry = {"_id": doc_id, "name": names.get(doc_id), "events referencing it": imp["events"]}
            if mode == "Teams":
                entry["players with currentTeamId"] = imp.get("players")
            impacts.append(entry)
        st.dataframe(viz.frame(impacts), hide_index=True)

        cascade = False
        if mode == "Teams":
            cascade = st.checkbox("Also delete this team's players (deleteMany on currentTeamId)", key=f"del_cascade_{nonce}")
        confirm = st.checkbox(f"I understand that {len(selected)} document(s) will be permanently deleted.",
                              key=f"del_confirm_{nonce}")
        if st.button("Delete", type="primary", disabled=not confirm):
            results = []
            for doc_id in selected:
                try:
                    if mode == "Players":
                        results.append(api.delete_player(doc_id))
                    else:
                        results.append(api.delete_team(doc_id, cascade_players=cascade))
                except api.ApiError as exc:
                    results.append({"id": doc_id, "error": str(exc)})
            st.session_state["del_results"] = results
            st.session_state["del_nonce"] = nonce + 1
            st.cache_data.clear()  # refresh sidebar counts
            st.rerun()
    else:
        st.caption("Tick one or more rows to see the impact and delete them.")

for result in st.session_state.get("del_results", []):
    with st.container(border=True):
        if result.get("error"):
            st.error(f"_id {result['id']}: {result['error']}")
            continue
        text = f"**_id {result['id']}**: deleted {result['deleted']} document(s)"
        if "players_kept" in result:
            text += f", deleted {result['deleted_players']} player(s), {result['players_kept']} player(s) kept"
        text += f", {result['events_kept']} event(s) kept."
        st.markdown(text)
        st.code(result["mongosh"], language="javascript")
