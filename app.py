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
    pd.DataFrame(columns=['Number', 'Name']).to_csv(ROSTER_FILE, index=False)

if not os.path.exists(LOG_FILE):
    pd.DataFrame(columns=['Date', 'Name', 'Status']).to_csv(LOG_FILE, index=False)

# --- HELPER FUNCTIONS ---
def load_data():
    roster = pd.read_csv(ROSTER_FILE)
    # Ensure roster has 'Number' column for backwards compatibility
    if 'Number' not in roster.columns:
        # Assign auto numbers starting at 1 for existing rows
        roster.insert(0, 'Number', range(1, len(roster) + 1))
        roster.to_csv(ROSTER_FILE, index=False)

    # Normalize Number column to string representation (preserve what user types where possible)
    try:
        # Attempt to convert numeric-like values to integers (so '1.0' doesn't appear)
        nums = pd.to_numeric(roster['Number'], errors='coerce')
        roster['Number'] = nums.where(nums.isna(), nums.astype('Int64').astype(str)).fillna(roster['Number'].astype(str))
    except Exception:
        roster['Number'] = roster['Number'].astype(str)

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

def save_roster(roster_df):
    # Save roster ensuring Number is saved as entered
    roster_df.to_csv(ROSTER_FILE, index=False)

# --- APP LAYOUT ---
st.set_page_config(page_title="Wolfpack Weight Room Tracker", page_icon="💪")
st.title("🏋️ Wolfpack Weight Room Attendance")

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
            
            # Create a row for each player sorted by Number (numeric where possible) then Name
            def sort_key(row):
                try:
                    n = int(row['Number'])
                except Exception:
                    # If Number is non-numeric or empty, sort after numeric ones
                    n = 10**9
                return (n, row['Name'].lower())
            
            roster_sorted = roster.copy()
            roster_sorted['__sort_key'] = roster_sorted.apply(sort_key, axis=1)
            roster_sorted = roster_sorted.sort_values('__sort_key').drop(columns='__sort_key')

            for _, row in roster_sorted.iterrows():
                player = row['Name']
                number = row['Number']
                display_label = f"{number} - {player}" if str(number).strip() != '' else player

                choices = ['Present', 'Absent', 'Tardy']
                key = f"radio_{player}"
                # Default to 'Absent' unless an existing record for the selected date says otherwise
                default_status = 'Absent'
                
                if not existing_for_day.empty:
                    record = existing_for_day[existing_for_day['Name'] == player]
                    if not record.empty:
                        status = record.iloc[0]['Status']
                        if status in choices:
                            default_status = status
                
                # Initialize session state for the radio if not present so it shows 'Absent' by default
                if key not in st.session_state:
                    st.session_state[key] = default_status
                else:
                    # If there's an existing record for the day, override session state with it
                    if not existing_for_day.empty and player in existing_for_day['Name'].values:
                        st.session_state[key] = default_status
                
                col1, col2 = st.columns([2, 3])
                with col1:
                    st.write(f"**{display_label}**")
                with col2:
                    # Set the radio with the session state default; coach can actively change it
                    attendance_data[player] = st.radio(
                        f"Status for {display_label}", 
                        choices,
                        index=choices.index(st.session_state[key]), 
                        key=key, 
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
        
        # Assuming Tardy counts as credit
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
        new_player = st.text_input("Player Name", key="new_player_name")
        new_number = st.text_input("Player Number (leave blank to skip)", key="new_player_number")
        if st.button("Add to Roster"):
            # Basic validation
            if not new_player:
                st.error("Please provide a player name.")
            else:
                # Normalize number to string (keeps whatever user types)
                num_str = str(new_number).strip()
                # Check duplicates by name or number (if provided)
                if new_player in roster['Name'].values:
                    st.error("Player already exists.")
                elif num_str != '' and num_str in roster['Number'].values:
                    st.error("That number is already assigned to another player.")
                else:
                    new_entry = pd.DataFrame([{'Number': num_str, 'Name': new_player}])
                    updated_roster = pd.concat([roster, new_entry], ignore_index=True)
                    save_roster(updated_roster)
                    st.success(f"Added {new_player} with number '{num_str or '(none)'}'")
                    st.rerun()
    
    with col2:
        st.subheader("Current Roster")
        st.write("Edit numbers below and press 'Save Roster Changes' to persist.")
        
        # Provide editable number inputs for each player
        edit_cols = st.columns([1, 3, 2])  # Number, Name, (spacer)
        edit_cols[0].markdown("**Number**")
        edit_cols[1].markdown("**Name**")
        edits = {}
        
        # Show rows in numeric order when possible
        def sort_key(row):
            try:
                n = int(row['Number'])
            except Exception:
                n = 10**9
            return (n, row['Name'].lower())
        
        roster_sorted = roster.copy()
        roster_sorted['__sort_key'] = roster_sorted.apply(sort_key, axis=1)
        roster_sorted = roster_sorted.sort_values('__sort_key').drop(columns='__sort_key').reset_index(drop=True)

        for idx, row in roster_sorted.iterrows():
            name = row['Name']
            number = row['Number']
            c_num, c_name = st.columns([1, 3])
            # Use text_input for number to allow non-numeric entries if desired
            new_num = c_num.text_input(f"num_{idx}", value=str(number), key=f"num_{idx}")
            c_name.write(f"**{name}**")
            edits[name] = new_num.strip()
        
        if st.button("Save Roster Changes"):
            # Validate duplicate numbers (excluding blank)
            nums = [v for v in edits.values() if v != ""]
            if len(nums) != len(set(nums)):
                st.error("Duplicate numbers detected. Each non-blank number must be unique.")
            else:
                # Build updated roster preserving the sorted display order
                updated_df = pd.DataFrame([{'Number': edits[name], 'Name': name} for name in roster_sorted['Name']])
                save_roster(updated_df)
                st.success("Roster updated.")
                st.rerun()
        
        st.markdown("---")
        st.dataframe(roster[['Number', 'Name']], height=300)
