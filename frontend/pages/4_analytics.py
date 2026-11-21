import datetime as dt

import streamlit as st

import api
import viz

st.title("Analytics")


@st.cache_data(ttl=300, show_spinner=False)
def catalog() -> list[dict]:
    return api.analytics_catalog()


try:
    queries = catalog()
    matches = api.matches()
except api.ApiError as exc:
    st.error(str(exc))
    st.stop()

match_labels = {m["_id"]: m["label"] for m in matches}


def param_inputs(query: dict) -> dict | None:
    """Render the inputs of one query. Returns the params, or None when a match is needed but missing."""
    values = {}
    columns = st.columns(max(len(query["params"]), 1))
    for column, p in zip(columns, query["params"]):
        key = f"{query['id']}_{p['name']}"
        with column:
            if p["type"] == "match":
                options = ([None] if p.get("allow_all") else []) + list(match_labels)
                if not options:
                    st.warning("No matches in the database yet. Ingest matches and events first.")
                    return None
                values[p["name"]] = st.selectbox(
                    p["label"], options, key=key,
                    format_func=lambda m: "All matches" if m is None else f"{match_labels[m]} ({m})")
            elif p["type"] == "float":
                values[p["name"]] = st.number_input(p["label"], value=float(p["default"]), min_value=float(p["min"]),
                                                    max_value=float(p["max"]), step=float(p["step"]), key=key)
            elif p["type"] == "int":
                values[p["name"]] = int(st.number_input(p["label"], value=int(p["default"]), min_value=int(p["min"]),
                                                        max_value=int(p["max"]), step=int(p["step"]), key=key))
            elif p["type"] == "date":
                picked = st.date_input(p["label"], value=dt.date.fromisoformat(p["default"]),
                                       min_value=dt.date(1960, 1, 1), max_value=dt.date.today(),
                                       format="YYYY-MM-DD", key=key)
                values[p["name"]] = picked.isoformat()
            else:
                values[p["name"]] = st.text_input(p["label"], value=p.get("default") or "", help=p.get("help"), key=key)
    return values


def query_card(query: dict) -> None:
    qid = query["id"]
    # 1. title + question + why
    st.subheader(f"{qid}. {query['title']}")
    st.markdown(f"**{query['question']}**")
    st.caption(f"Why it matters: {query['why']}")

    # 2. params + Run
    params = param_inputs(query)
    if params is None:
        return
    if st.button("Run", key=f"run_{qid}", type="primary"):
        st.session_state.pop(f"warn_{qid}", None)
        st.session_state.pop(f"res_{qid}", None)
        try:
            with st.spinner("Running on Atlas..."):
                st.session_state[f"res_{qid}"] = api.run_query(qid, params)
        except api.ApiError as exc:
            st.session_state[f"warn_{qid}"] = (exc.status, str(exc))

    warning = st.session_state.get(f"warn_{qid}")
    if warning:
        status, message = warning
        (st.warning if status == 422 else st.error)(message)
        return
    result = st.session_state.get(f"res_{qid}")
    if not result:
        return

    # 3. mongosh, 4. Python (both generated from the spec that ran)
    st.markdown("**mongosh**")
    st.code(result["mongosh"], language="javascript")
    st.markdown("**Python**")
    st.code(result["python"], language="python")

    # 5. result visual + raw rows
    st.markdown(f"**Result** ({len(result['rows'])} row(s), params: `{result['params']}`)")
    viz.render(result)
    with st.expander("Raw rows"):
        st.json(result["rows"], expanded=False)
        for name, rows in (result.get("extra") or {}).items():
            st.caption(f"{name} pipeline")
            st.json(rows, expanded=False)


tabs = st.tabs(["Find (Read)", "Aggregations"])
for tab, kind in zip(tabs, ["find", "aggregate"]):
    with tab:
        options = [q for q in queries if q["kind"] == kind]
        by_id = {q["id"]: q for q in options}
        chosen = st.selectbox("Query", list(by_id), key=f"pick_{kind}",
                              format_func=lambda i: f"{i}. {by_id[i]['question']}")
        query_card(by_id[chosen])
