"""
Interactive Streamlit Frontend for Thesis Simulation Engine
Shows step-by-step simulation with queue visualization and request details
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import sys
import os

# Add project root to path so frontend1 can import backend1 modules reliably
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend1.scheduler_engine1 import (
    SimulationEngine, DocumentRequest, COLLEGES, DOCUMENT_COMPLEXITY, 
    COLLEGE_POPULATION, REQUESTER_PRIORITY
)

# ============================================================================
# STREAMLIT PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="Thesis Simulation Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Registrar Queue Simulation Dashboard")

# ============================================================================
# SIDEBAR CONTROLS
# ============================================================================

st.sidebar.header("🎛️ Simulation Parameters")

scheduler_type = st.sidebar.selectbox(
    "Scheduler Type",
    ["FCFS"],
    help="FCFS: First-Come-First-Served"
)

allocator_type = st.sidebar.selectbox(
    "Allocator Strategy",
    ["college_based", "workload_based", "pooled", "quota_free"],
    help="How to assign requests to staff"
)

num_staff = st.sidebar.slider(
    "Number of Staff",
    min_value=1,
    max_value=6,
    value=6,
    help="1 staff per college (6 colleges total)"
)

total_requests = st.sidebar.slider(
        "Total Daily Requests", min_value=50, max_value=500, value=200, step=10,
        help="Volume of requests arriving in one day"
    )

enable_absence = st.sidebar.checkbox("Enable Staff Absence", value=False)
num_absent = 0
if enable_absence:
    num_absent = st.sidebar.slider(
        "Number of Absent Staff", min_value=1, max_value=max(1, num_staff-1), value=1, step=1,
        help="Staff removed before simulation starts"
    )

urgency_base = st.sidebar.slider(
    "Average Urgency Level (1-10)", min_value=1, max_value=10, value=5, step=1,
    help="Higher = more urgent requests in the queue"
    )

imbalance_factor = st.sidebar.slider(
    "College Workload Imbalance (0-100%)", min_value=0, max_value=100, value=0, step=5,
    help="0% = balanced across colleges, 100% = COE gets heavy overload"
    )


quota_limit = st.sidebar.slider(
    "Daily Quota per Staff",
    min_value=5,
    max_value=50,
    value=20,
    step=5,
    help="Max requests per staff per day"
)

st.sidebar.subheader("Reproducibility")
seed_mode = st.sidebar.radio("Seed Mode", ["Auto", "Manual"], index=0)
if seed_mode == "Manual":
    manual_seed = st.sidebar.number_input(
        "Random Seed", 
        min_value=1, 
        max_value=2_147_483_647, 
        value=12345
    )
else:
    manual_seed = None

# ============================================================================
# RUN SIMULATION
# ============================================================================

# Initialize session state for results
if "simulation_engine" not in st.session_state:
    st.session_state.simulation_engine = None
if "simulation_results" not in st.session_state:
    st.session_state.simulation_results = None

if st.sidebar.button("🚀 RUN SIMULATION", use_container_width=True):
    with st.spinner("⏳ Running simulation..."):
        # Calculate effective staff (total - absent)
        effective_staff = max(1, num_staff - num_absent)
        
        # Build custom config dict
        custom_config = {
            "total_requests": total_requests,
            "enable_absence": enable_absence,
            "num_absent_staff": num_absent,
            "urgency_base": urgency_base,
            "imbalance_factor": imbalance_factor
        }
        
        engine = SimulationEngine(
            scheduler_type=scheduler_type,
            allocator_type=allocator_type,
            staff_config={
                "enable_custom_staff": True,
                "num_staff": effective_staff,  
                "quota_limit": quota_limit
            },
            random_seed=manual_seed
        )
        results = engine.run(custom_config=custom_config) 
        
        # Store in session state (persists across interactions)
        st.session_state.simulation_engine = engine
        st.session_state.simulation_results = results

        if 'seed_used' in results:
            st.sidebar.success(f"✅ Run complete (Seed: {results['seed_used']})")

# ============================================================================
# DISPLAY RESULTS
# ============================================================================

if st.session_state.simulation_results and st.session_state.simulation_engine:
    engine = st.session_state.simulation_engine
    results = st.session_state.simulation_results
    
    st.success("✅ Simulation Complete!")
    
    # ========================================================================
    # KEY METRICS (Top Cards)
    # ========================================================================
    
    st.header("📈 Key Metrics")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        processed = results['total_processed']
        expected = total_requests
        completion_pct = (processed / expected * 100) if expected > 0 else 0
        st.metric(
            "Total Processed",
            f"{processed}/{expected}",
            delta=f"{completion_pct:.0f}%" if completion_pct == 100 else f"{completion_pct:.0f}%"
        )
    
    with col2:
        st.metric(
            "Days Elapsed",
            f"{results['total_days_elapsed']:.1f}d",
            help="Total simulation duration"
        )
    
    with col3:
        st.metric(
            "Avg Queue Wait",
            f"{results['avg_waiting_time_hours']:.1f}h",
            delta=f"{results['avg_waiting_time_hours']/24:.1f}d" if results['avg_waiting_time_hours'] > 24 else None
        )
    
    with col4:
        st.metric(
            "Avg Turnaround",
            f"{results['avg_turnaround_days']:.1f}d",
            help="From submission to completion"
        )
    
    with col5:
        st.metric(
            "Throughput",
            f"{results['throughput_req_per_day']:.2f}",
            help="Requests per day"
        )

    # ========================================================================
    # EVENT LOG VISUALIZATION
    # ========================================================================
    
    st.header("📋 Event Log")
    
    event_log = results.get("event_log", [])
    
    if event_log:
        # Filter controls
        col1, col2, col3 = st.columns(3)
        with col1:
            filter_event_type = st.multiselect(
                "Event Type",
                options=["ARRIVAL", "ASSIGN", "COMPLETE", "WAITING"],
                default=["ARRIVAL", "ASSIGN", "COMPLETE", "WAITING"],
                key="filter_event_type"
            )
        with col2:
            filter_college = st.multiselect(
                "College",
                options=["All"] + COLLEGES,
                default=["All"],
                key="filter_college_events"
            )
        with col3:
            max_events = st.slider(
                "Max Events to Show", 
                min_value=10, 
                max_value=len(event_log), 
                value=min(100, len(event_log)), 
                key="max_events"
            )
        
        # Filter events
        filtered_events = [
            ev for ev in event_log 
            if ev.get("event_type") in filter_event_type
            and (filter_college == ["All"] or ev.get("college") in filter_college)
        ][:max_events]
        
        # Convert to DataFrame
        if filtered_events:
            event_df = pd.DataFrame(filtered_events)
            
            # Format time column for display
            event_df["Time"] = pd.to_datetime(event_df["time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
            
            # Select and rename columns for clean display
            display_cols = ["sequence", "Time", "event_type", "request_id", "college", "staff_id", "details"]
            if all(col in event_df.columns for col in display_cols):
                display_df = event_df[display_cols].copy()
                display_df.columns = ["#", "Time", "Event Type", "Request ID", "College", "Staff", "Details"]
                
                # Color code by event type for better readability
                def color_event_type(val):
                    colors = {
                        "ARRIVAL": "#e3f2fd",    # Light blue
                        "ASSIGN": "#c8e6c9",     # Light green
                        "COMPLETE": "#a5d6a7",   # Green
                        "WAITING": "#ffebee"     # Light red
                    }
                    return f"background-color: {colors.get(val, 'white')}"
                
                st.dataframe(
                    display_df.style.applymap(color_event_type, subset=["Event Type"]),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Event statistics summary
                st.subheader("📊 Event Statistics")
                stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)
                
                event_counts = display_df["Event Type"].value_counts()
                
                with stats_col1:
                    st.metric("Total Events", len(display_df))
                with stats_col2:
                    st.metric("Arrivals", event_counts.get("ARRIVAL", 0))
                with stats_col3:
                    st.metric("Assignments", event_counts.get("ASSIGN", 0))
                with stats_col4:
                    st.metric("Waiting (Unassigned)", event_counts.get("WAITING", 0))
                
                # Timeline chart: Events by hour
                st.subheader("📈 Event Timeline")
                if "Time" in event_df.columns:
                    timeline_df = event_df.copy()
                    timeline_df["Hour"] = pd.to_datetime(timeline_df["Time"]).dt.hour
                    
                    fig_timeline = px.histogram(
                        timeline_df,
                        x="Hour",
                        color="Event Type",
                        title="Events by Hour of Simulation Day",
                        labels={"Hour": "Hour of Day (8 AM = 8, 5 PM = 17)", "count": "Number of Events"},
                        color_discrete_map={
                            "ARRIVAL": "#2196f3",
                            "ASSIGN": "#4caf50",
                            "COMPLETE": "#8bc34a",
                            "WAITING": "#f44336"
                        },
                        nbins=24
                    )
                    fig_timeline.update_layout(xaxis=dict(tickmode='linear', tick0=8, dtick=1))
                    st.plotly_chart(fig_timeline, use_container_width=True)
        else:
            st.info("No events match the selected filters.")
    else:
        st.warning("No event log available. Ensure your backend returns 'event_log' in results.")
    
    # ========================================================================
    # ABSENT STAFF SECTION
    # ========================================================================
    
    if results.get('absent_staff'):
        st.warning(f"⚠️ **ABSENT STAFF:** {', '.join(results['absent_staff'])}")
    
    # ========================================================================
    # WAITING QUEUE SECTION
    # ========================================================================
    
    waiting_queue = results.get('waiting_queue', [])
    if waiting_queue:
        st.header("📋 Waiting Queue (Unassigned Requests)")
        st.info(f"**{len(waiting_queue)} requests** stuck in queue due to missing staff")
        
        # Build waiting queue table
        waiting_data = []
        for idx, req in enumerate(waiting_queue, 1):
            waiting_data.append({
                "Order": idx,
                "Request ID": req.request_id,
                "College": req.college,
                "Document": req.document_type,
                "Urgency": req.urgency,
                "Requester": req.requester_type,
                "Submitted": req.submission_time.strftime("%H:%M")
            })
        
        waiting_df = pd.DataFrame(waiting_data)
        st.dataframe(waiting_df, use_container_width=True, hide_index=True)

    
    # ========================================================================
    # QUEUE WAIT ANALYSIS
    # ========================================================================
    
    st.header("⏱️ Queue Wait Analysis")
    
    if event_log:
        # Extract assignment events with queue wait info
        assign_events = [ev for ev in event_log if ev.get("event_type") == "ASSIGN" and ev.get("queue_wait_hours") is not None]
        
        if assign_events:
            wait_data = []
            for ev in assign_events:
                wait_data.append({
                    "Request ID": ev.get("request_id"),
                    "College": ev.get("college"),
                    "Staff": ev.get("staff_id"),
                    "Queue Wait (h)": ev.get("queue_wait_hours", 0),
                    "Processing Hours": ev.get("processing_hours", 0),
                    "Time": ev.get("time")
                })
            
            wait_df = pd.DataFrame(wait_data)
            
            # Summary statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Avg Queue Wait", f"{wait_df['Queue Wait (h)'].mean():.2f} h")
            with col2:
                st.metric("Max Queue Wait", f"{wait_df['Queue Wait (h)'].max():.2f} h")
            with col3:
                st.metric("Min Queue Wait", f"{wait_df['Queue Wait (h)'].min():.2f} h")
            with col4:
                st.metric("Requests with >24h Wait", len(wait_df[wait_df["Queue Wait (h)"] > 24]))
            
            # Distribution chart
            fig_wait = px.histogram(
                wait_df,
                x="Queue Wait (h)",
                nbins=30,
                title="Distribution of Queue Wait Times",
                labels={"Queue Wait (h)": "Queue Wait (hours)"},
                color_discrete_sequence=["#ff9800"]
            )
            st.plotly_chart(fig_wait, use_container_width=True)
            
            # Show requests with longest waits
            st.subheader("🔴 Longest Queue Waits (Top 10)")
            longest_waits = wait_df.nlargest(10, "Queue Wait (h)")
            st.dataframe(longest_waits, use_container_width=True, hide_index=True)
    
    # ========================================================================
    # STAFF LOAD DISTRIBUTION (Bar Chart)
    # ========================================================================
    
    st.header("👥 Staff Load Distribution")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        staff_load_data = results['staff_load']
        staff_ids = list(staff_load_data.keys())
        loads = list(staff_load_data.values())
        
        fig = go.Figure(data=[
            go.Bar(
                x=staff_ids,
                y=loads,
                marker=dict(
                    color=loads,
                    colorscale='Viridis',
                    showscale=True
                ),
                text=loads,
                textposition='outside'
            )
        ])
        fig.update_layout(
            title="Requests per Staff Member",
            xaxis_title="Staff",
            yaxis_title="Number of Requests",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Load Stats")
        loads_list = list(staff_load_data.values())
        st.write(f"**Max Load:** {max(loads_list)} requests")
        st.write(f"**Min Load:** {min(loads_list)} requests")
        st.write(f"**Avg Load:** {sum(loads_list)/len(loads_list):.1f} requests")
        st.write(f"**Imbalance:** {max(loads_list) - min(loads_list)} requests")
    
    # ========================================================================
    # COLLEGE DISTRIBUTION (Pie Chart)
    # ========================================================================
    
    st.header("🏫 College Distribution")
    
    college_counts = {}
    for req in engine.completed:
        college_counts[req.college] = college_counts.get(req.college, 0) + 1
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = go.Figure(data=[
            go.Pie(
                labels=list(college_counts.keys()),
                values=list(college_counts.values()),
                hole=0
            )
        ])
        fig.update_layout(title="Requests by College")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        college_df = pd.DataFrame([
            {"College": col, "Count": count, "Percentage": f"{count/sum(college_counts.values())*100:.1f}%"}
            for col, count in sorted(college_counts.items(), key=lambda x: x[1], reverse=True)
        ])
        st.dataframe(college_df, use_container_width=True, hide_index=True)
    
    # ========================================================================
    # QUEUE WAIT TIME ANALYSIS (Distribution)
    # ========================================================================
    
    st.header("⏱️ Queue Wait Time Distribution")
    
    queue_waits = []
    for req in engine.completed:
        wait_hours = (req.assignment_time - req.submission_time).total_seconds() / 3600
        queue_waits.append(wait_hours)
    
    fig = go.Figure(data=[
        go.Histogram(
            x=queue_waits,
            nbinsx=30,
            marker_color='rgba(0, 100, 80, 0.7)',
        )
    ])
    fig.update_layout(
        title="Distribution of Queue Wait Times",
        xaxis_title="Queue Wait (hours)",
        yaxis_title="Number of Requests",
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # ========================================================================
    # TIMELINE VISUALIZATION (Requests by Day)
    # ========================================================================
    
    st.header("📅 Assignment Timeline")
    
    timeline_data = []
    for req in engine.completed:
        assignment_day = int((req.assignment_time - engine.start_time).total_seconds() / 86400) + 1
        timeline_data.append({
            "Day": assignment_day,
            "College": req.college,
            "Count": 1
        })
    
    timeline_df = pd.DataFrame(timeline_data)
    timeline_grouped = timeline_df.groupby(["Day", "College"]).size().reset_index(name="Count")
    
    fig = px.bar(
        timeline_grouped,
        x="Day",
        y="Count",
        color="College",
        title="Requests Assigned Per Day by College",
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # ========================================================================
    # INTERACTIVE REQUEST BROWSER
    # ========================================================================
    
    st.header("🔍 Browse Individual Requests")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filter_college = st.selectbox(
            "Filter by College",
            ["All"] + COLLEGES,
            key="college_filter"
        )
    
    with col2:
        filter_document = st.selectbox(
            "Filter by Document Type",
            ["All"] + list(DOCUMENT_COMPLEXITY.keys()),
            key="doc_filter"
        )
    
    with col3:
        sort_by = st.selectbox(
            "Sort by",
            ["Assigned Day (then Submission)", "Submission Time", "Queue Wait (desc)", "Queue Wait (asc)", "Turnaround (desc)"],
            index=0
        )
    
    # Apply filters
    filtered_requests = engine.completed
    
    if filter_college != "All":
        filtered_requests = [r for r in filtered_requests if r.college == filter_college]
    
    if filter_document != "All":
        filtered_requests = [r for r in filtered_requests if r.document_type == filter_document]
    
    # Sort
    if sort_by == "Assigned Day (then Submission)":
        filtered_requests = sorted(
            filtered_requests,
            key=lambda r: (
                int((r.assignment_time - engine.start_time).total_seconds() / 86400),
                r.submission_time
            )
        )
    elif sort_by == "Queue Wait (desc)":
        filtered_requests = sorted(
            filtered_requests,
            key=lambda r: (r.assignment_time - r.submission_time).total_seconds(),
            reverse=True
        )
    elif sort_by == "Queue Wait (asc)":
        filtered_requests = sorted(
            filtered_requests,
            key=lambda r: (r.assignment_time - r.submission_time).total_seconds()
        )
    elif sort_by == "Turnaround (desc)":
        filtered_requests = sorted(
            filtered_requests,
            key=lambda r: (r.completion_time - r.submission_time).total_seconds(),
            reverse=True
        )
    else:  # Submission Time
        filtered_requests = sorted(filtered_requests, key=lambda r: r.submission_time)
    
    # Display table
    st.subheader(f"Showing {len(filtered_requests)} requests (sorted by {sort_by})")
    
    request_table_data = []
    for arrival_order, req in enumerate(filtered_requests):
        queue_wait = (req.assignment_time - req.submission_time).total_seconds() / 3600
        turnaround = (req.completion_time - req.submission_time).total_seconds() / 86400
        assignment_day = int((req.assignment_time - engine.start_time).total_seconds() / 86400) + 1
        
        request_table_data.append({
            "Arrival #": arrival_order,
            "Request": req.request_id,
            "College": req.college,
            "Document": req.document_type,
            "Urgency": req.urgency,
            "Requester": req.requester_type,
            "Queue Wait (h)": f"{queue_wait:.1f}",
            "Turnaround (d)": f"{turnaround:.2f}",
            "Assigned Day": assignment_day,
            "Staff": req.assigned_staff
        })
    
    request_df = pd.DataFrame(request_table_data)
    
    # Make it clickable
    selected_row = st.dataframe(
        request_df,
        use_container_width=True,
        hide_index=True,
        key="request_table"
    )
    
    # Request details picker
    st.subheader("📋 Request Details")
    
    request_idx = st.number_input(
        "Select Request ID to View Details",
        min_value=0,
        max_value=len(filtered_requests)-1,
        help="Enter the ID from the table above"
    )
    
    if request_idx < len(filtered_requests):
        selected_req = filtered_requests[request_idx]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(f"Request {selected_req.request_id}")
            st.write(f"**College:** {selected_req.college}")
            st.write(f"**Document Type:** {selected_req.document_type}")
            st.write(f"**Urgency Level:** {selected_req.urgency}/10")
            st.write(f"**Requester Type:** {selected_req.requester_type}")
            st.write(f"**Assigned Staff:** {selected_req.assigned_staff}")
        
        with col2:
            st.subheader("Timeline")
            
            arrival_time = selected_req.submission_time.strftime("%Y-%m-%d %H:%M")
            assignment_time = selected_req.assignment_time.strftime("%Y-%m-%d %H:%M")
            completion_time = selected_req.completion_time.strftime("%Y-%m-%d %H:%M")
            
            st.write(f"**Arrival (Submission):** {arrival_time}")
            st.write(f"**Assignment:** {assignment_time}")
            st.write(f"**Completion:** {completion_time}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            queue_wait_hours = (selected_req.assignment_time - selected_req.submission_time).total_seconds() / 3600
            st.metric("Queue Wait Time", f"{queue_wait_hours:.1f} hours", delta=f"{queue_wait_hours/24:.2f} days")
        
        with col2:
            process_days = (selected_req.completion_time - selected_req.assignment_time).total_seconds() / 86400
            st.metric("Processing Time", f"{process_days:.2f} days", delta=f"{process_days*24:.1f} hours")
        
        # Timeline visualization for this request
        st.subheader("Request Lifecycle")
        
        timeline_events = [
            {
                "Event": "Submitted",
                "Time": selected_req.submission_time,
                "Status": "Waiting in Queue",
                "Color": "orange"
            },
            {
                "Event": f"Assigned to {selected_req.assigned_staff}",
                "Time": selected_req.assignment_time,
                "Status": "In Progress",
                "Color": "blue"
            },
            {
                "Event": "Completed",
                "Time": selected_req.completion_time,
                "Status": "Done",
                "Color": "green"
            }
        ]
        
        timeline_df = pd.DataFrame(timeline_events)
        
        fig = go.Figure()
        for idx, event in enumerate(timeline_events):
            fig.add_trace(go.Scatter(
                x=[event["Time"]],
                y=[idx],
                mode='markers+text',
                name=event["Event"],
                text=[event["Event"]],
                textposition="top center",
                marker=dict(size=15, color=event["Color"])
            ))
        
        fig.update_layout(
            title="Request Lifecycle Timeline",
            xaxis_title="Time",
            yaxis_title="",
            height=300,
            showlegend=False,
            yaxis=dict(showticklabels=False)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # ========================================================================
    # COMPARISON SECTION
    # ========================================================================
    
    st.header("📊 Run Comparison")
    
    if st.button("Compare with Different Allocator", use_container_width=True):
        st.info("ℹ️ This would run simulations with different allocators and show comparison")
    
    # ========================================================================
    # EXPORT DATA
    # ========================================================================
    
    st.header("💾 Export Results")
    
    export_data = {
        "Request ID": [r.request_id for r in engine.completed],
        "College": [r.college for r in engine.completed],
        "Document Type": [r.document_type for r in engine.completed],
        "Urgency": [r.urgency for r in engine.completed],
        "Requester Type": [r.requester_type for r in engine.completed],
        "Submission Time": [r.submission_time for r in engine.completed],
        "Assignment Time": [r.assignment_time for r in engine.completed],
        "Completion Time": [r.completion_time for r in engine.completed],
        "Queue Wait (hours)": [(r.assignment_time - r.submission_time).total_seconds() / 3600 for r in engine.completed],
        "Turnaround (days)": [(r.completion_time - r.submission_time).total_seconds() / 86400 for r in engine.completed],
        "Assigned Staff": [r.assigned_staff for r in engine.completed]
    }
    
    export_df = pd.DataFrame(export_data)
    
    csv = export_df.to_csv(index=False)
    st.download_button(
        label="📥 Download Results as CSV",
        data=csv,
        file_name=f"simulation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True
    )

else:
    st.info("👈 Configure parameters on the left and click 'RUN SIMULATION' to begin")
