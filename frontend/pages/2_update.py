import datetime as dt

import streamlit as st

import api
import viz

READ_ONLY = {"verifiedAt"}  # managed by the bulk operations
BULK_LABELS = {
    "set_verified": "$set verifiedAt = now",
    "unset_verified": "$unset verifiedAt",
    "set_value": "$set marketValueEUR",
    "mul_value": "$mul marketValueEUR (e.g. 1.1 = +10%)",
    "push_tag": "$push one tag",
    "push_tags": "$push several tags ($each)",
    "pull_tag": "$pull a tag",
}

st.title("Update documents")
st.caption("Tick rows in the table, edit the fields below, then save. Only changed fields are sent; "
           "emptied text fields are removed with $unset; every change is logged in editHistory.")


def is_empty(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def same(old, new) -> bool:
    if is_empty(old) and is_empty(new):
        return True
    if isinstance(old, (int, float)) and isinstance(new, (int, float)) and not isinstance(old, bool):
        return float(old) == float(new)
    return old == new


def field_input(path: str, value, key: str):
    """One widget per flattened field. Returns the new value (or the old one for read-only fields)."""
    if path in READ_ONLY:
        st.text_input(path, value="" if value is None else str(value), disabled=True, key=key)
        return value
    if path == "birthDate":
        try:
            current = dt.date.fromisoformat(str(value)[:10]) if value else None
        except ValueError:
            current = None
        picked = st.date_input(path, value=current, min_value=dt.date(1940, 1, 1), max_value=dt.date.today(),
                               format="YYYY-MM-DD", key=key)
        return picked.isoformat() if picked else None
    if isinstance(value, bool):
        return st.checkbox(path, value=value, key=key)
    if isinstance(value, int):
        return int(st.number_input(path, value=value, step=1, key=key))
    if isinstance(value, float):
        return float(st.number_input(path, value=value, step=0.01, format="%.4f", key=key))
    return st.text_input(path, value="" if value is None else str(value), key=key)


mode = st.radio("Collection", ["Players", "Teams"], horizontal=True, key="upd_mode")

try:
    teams = api.teams()
    team_id = None
    if mode == "Players":
        team_names = {t["id"]: f"{t['name']} ({t['id']})" for t in teams}
        team_id = st.selectbox("Team", [None] + list(team_names),
                               format_func=lambda i: "All teams" if i is None else team_names[i], key="upd_team")
        rows = api.players(team_id)
    else:
        rows = teams
except api.ApiError as exc:
    st.error(str(exc))
    st.stop()

if not rows:
    st.info("No documents yet. Ingest some data first.")
    st.stop()

results_key = f"upd_results_{mode}"  # players and teams keep separate results
nonce = st.session_state.setdefault("upd_nonce", 0)  # new table key after saving = ticks cleared

saved = st.session_state.pop("upd_saved", None)
if saved:
    st.success(f"Saved changes for: {', '.join(saved)}")
    st.toast("Changes saved")

selected = viz.selection_table(rows, key=f"upd_table_{mode}_{team_id}_{nonce}")

# ---------------------------------------------------------------- edit form
if selected:
    get_doc = api.player if mode == "Players" else api.team
    patch = api.patch_players if mode == "Players" else api.patch_teams
    with st.form("edit_form"):
        collected, titles = {}, {}
        for doc_id in selected:
            try:
                item = get_doc(doc_id)
            except api.ApiError as exc:
                st.error(str(exc))
                continue
            title = item["doc"].get("shortName") or item["doc"].get("name") or doc_id
            titles[doc_id] = str(title)
            with st.expander(f"{title} (_id {doc_id})", expanded=True):
                st.text_input("wyId", value=str(item["doc"].get("wyId", doc_id)), disabled=True, key=f"ro_{mode}_{doc_id}")
                values = {}
                for path, old in item["flat"].items():
                    values[path] = (old, field_input(path, old, key=f"f_{mode}_{doc_id}_{path}"))
                collected[doc_id] = values
        submitted = st.form_submit_button("Save changes", type="primary")

    if submitted:
        items = []
        for doc_id, values in collected.items():
            changes = {p: new for p, (old, new) in values.items() if p not in READ_ONLY and not same(old, new)}
            if changes:
                items.append({"id": doc_id, "changes": changes})
        if not items:
            st.info("Nothing changed.")
        else:
            try:
                results = patch(items)
                st.session_state[results_key] = results
                st.session_state["upd_saved"] = [titles[r["id"]] for r in results if r.get("diff")]
                st.session_state["upd_nonce"] = nonce + 1
                st.rerun()
            except api.ApiError as exc:
                st.error(str(exc))
else:
    st.caption("Tick one or more rows to edit them.")

for result in st.session_state.get(results_key, []):
    with st.container(border=True):
        if result.get("error"):
            st.error(f"_id {result['id']}: {result['error']}")
            continue
        st.markdown(f"**_id {result['id']}**: {len(result['diff'])} field(s) changed")
        if result["diff"]:
            st.dataframe(viz.frame(result["diff"]), hide_index=True)
        if result.get("mongosh"):
            st.code(result["mongosh"], language="javascript")
        if result.get("editHistory"):
            st.caption("Latest editHistory entries")
            st.dataframe(viz.frame(result["editHistory"]), hide_index=True)

# ---------------------------------------------------------------- bulk operations
if mode == "Players":
    with st.expander("Bulk operations (team players)"):
        team_names = {t["id"]: f"{t['name']} ({t['id']})" for t in teams}
        if not team_names:
            st.info("No teams yet.")
        else:
            default = list(team_names).index(team_id) if team_id in team_names else 0
            bulk_team = st.selectbox("Team", list(team_names), index=default, format_func=team_names.get, key="bulk_team")
            op = st.selectbox("Operation", list(BULK_LABELS), format_func=lambda o: f"{o}: {BULK_LABELS[o]}", key="bulk_op")
            value = None
            if op == "set_value":
                value = st.number_input("Market value (EUR)", value=1_000_000.0, step=100_000.0, key="bulk_set")
            elif op == "mul_value":
                value = st.number_input("Multiply by", value=1.1, step=0.05, key="bulk_mul")
                st.caption("Players without marketValueEUR get 0 ($mul on a missing field sets it to 0).")
            elif op in ("push_tag", "pull_tag"):
                value = st.text_input("Tag", value="shortlist", key="bulk_tag")
            elif op == "push_tags":
                raw = st.text_input("Tags (comma separated)", value="scouted, u21-watch", key="bulk_tags")
                value = [t.strip() for t in raw.split(",") if t.strip()]
            if st.button("Apply to all players of this team", key="bulk_apply"):
                try:
                    st.session_state["bulk_result"] = api.bulk_players(bulk_team, op, value)
                    st.rerun()
                except api.ApiError as exc:
                    st.error(str(exc))
            res = st.session_state.get("bulk_result")
            if res:
                c1, c2 = st.columns(2)
                c1.metric("matched_count", res["matched_count"])
                c2.metric("modified_count", res["modified_count"])
                st.code(res["mongosh"], language="javascript")

if st.session_state.get(results_key) and st.button("Clear results"):
    st.session_state.pop(results_key, None)
    st.rerun()
