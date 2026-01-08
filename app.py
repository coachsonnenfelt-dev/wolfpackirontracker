import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta

# --- CONFIGURATION ---
ROSTER_FILE = 'roster.csv'
LOG_FILE = 'attendance_log.csv'
WEEKLY_GOAL = 4

# --- SETUP FILES IF THEY DON'T EXIST ---
if not os.path.exists(ROSTER_FILE):
    pd.DataFrame(columns=['Name']).to_csv(ROSTER_FILE, index=False)

if not os.path.exists(LOG_FILE):
    pd.DataFrame(columns=['Date', 'Name', 'Status']).to_csv(LOG_FILE, index=False)

# --- HELPER FUNCTIONS ---
def load_data():
    roster = pd.read_csv(ROSTER_FILE)
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0:
        logs = pd.read_csv(LOG_FILE)
        # Ensure Date is datetime objects for filtering
        logs['Date'] = pd.to_datetime(logs['Date']).dt.date
    else:
        logs = pd.DataFrame(columns=['Date', 'Name', 'Status'])
    return roster, logs

def save_attendance(date, attendance_data):
    # Load current logs
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0:
        current_logs = pd.read_csv(LOG_FILE)
        current_logs['Date'] = pd.to_datetime(current_logs['Date']).dt.date
    else:
        current_logs = pd.DataFrame(columns=['Date', 'Name', 'Status'])

    # Create new entries
    new_entries = []
    for name, status in attendance_data.items():
        new_entries.append({'Date': date, 'Name': name, 'Status': status})
    
    new_df = pd.DataFrame(new_entries)
    
    # Remove old entries for this specific date (to allow overwriting/corrections)
    current_logs = current_logs[current_logs['Date'] != date]
    
    # Combine and save
    updated_logs = pd.concat([current_logs, new_df], ignore_index=True)
    updated_logs.to_csv(LOG_FILE, index=False)
    return True

# --- APP LAYOUT ---
st.set_page_config(page_title="Weight Room Tracker", page_icon="💪")
st.title("🏋️ Weight Room Attendance")

tab1, tab2, tab3 = st.tabs(["📝 Daily Log", "📊 Weekly Stats", "👥 Roster Management"])

# Load Data
roster, logs = load_data()

# --- TAB 1: DAILY LOG ---
with tab1:
    st.header("Take Attendance")
    
    # Date Selector
    selected_date = st.date_input("Select Date", datetime.now())
    
    if roster.empty:
        st.warning("Your roster is empty. Go to the 'Roster Management' tab to add players.")
    else:
        with st.form("attendance_form"):
            attendance_data = {}
            st.write(f"**Log for {selected_date.strftime('%A, %B %d')}**")
            
            # Check if data already exists for this day to pre-fill
            existing_for_day = logs[logs['Date'] == selected_date]
            
            # Create a row for each player
            for player in roster['Name'].sort_values():
                # Default status
                default_idx = 1 # Absent by default
                
                # If we have a record, use that
                if not existing_for_day.empty:
                    record = existing_for_day[existing_for_day['Name'] == player]
                    if not record.empty:
                        status = record.iloc[0]['Status']
                        if status == 'Present': default_idx = 0
                        elif status == 'Absent': default_idx = 1
                        elif status == 'Tardy': default_idx = 2
                
                col1, col2 = st.columns([2, 3])
                with col1:
                    st.write(f"**{player}**")
                with col2:
                    attendance_data[player] = st.radio(
                        f"Status for {player}", 
                        ['Present', 'Absent', 'Tardy'], 
                        index=default_idx, 
                        key=f"radio_{player}", 
                        horizontal=True,
                        label_visibility="collapsed"
                    )
                st.markdown("---")
            
            submit_button = st.form_submit_button("Save Attendance")
            
            if submit_button:
                save_attendance(selected_date, attendance_data)
                st.success(f"Attendance saved for {selected_date}!")
                # Force reload to update stats immediately
                st.rerun()

# --- TAB 2: WEEKLY STATS ---
with tab2:
    st.header("Weekly Compliance")
    
    # Calculate current week start (Monday)
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    st.write(f"**Current Week:** {start_of_week} to {end_of_week}")
    
    if logs.empty:
        st.info("No attendance data logged yet.")
    else:
        # Filter for this week
        mask = (logs['Date'] >= start_of_week) & (logs['Date'] <= end_of_week)
        weekly_logs = logs.loc[mask]
        
        # Filter for credit (Present or Tardy counts as credit?)
        # Assuming Tardy counts as a workout, just late.
        credit_logs = weekly_logs[weekly_logs['Status'].isin(['Present', 'Tardy'])]
        
        # Count workouts per player
        counts = credit_logs['Name'].value_counts().reindex(roster['Name'], fill_value=0)
        
        # Create DataFrame for display
        stats_df = pd.DataFrame({'Workouts': counts})
        stats_df['Status'] = stats_df['Workouts'].apply(
            lambda x: '✅ Goal Met' if x >= WEEKLY_GOAL else f'⚠️ Needs {WEEKLY_GOAL - x} more'
        )
        
        # Display with highlighting
        def highlight_rows(row):
            if row['Workouts'] >= WEEKLY_GOAL:
                return ['background-color: #d4edda'] * len(row)
            else:
                return ['background-color: #f8d7da'] * len(row)
                
        st.dataframe(stats_df.style.apply(highlight_rows, axis=1), use_container_width=True)

# --- TAB 3: ROSTER MANAGEMENT ---
with tab3:
    st.header("Manage Roster")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Add Player")
        new_player = st.text_input("Player Name")
        if st.button("Add to Roster"):
            if new_player and new_player not in roster['Name'].values:
                new_entry = pd.DataFrame([{'Name': new_player}])
                updated_roster = pd.concat([roster, new_entry], ignore_index=True)
                updated_roster.to_csv(ROSTER_FILE, index=False)
                st.success(f"Added {new_player}")
                st.rerun()
            elif new_player in roster['Name'].values:
                st.error("Player already exists.")
    
    with col2:
        st.subheader("Current Roster")
        st.dataframe(roster, height=300)
