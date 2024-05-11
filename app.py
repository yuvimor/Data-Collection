import streamlit as st
import pandas as pd
import serial
import time
import numpy as np
from scipy.signal import butter, lfilter, iirnotch
import matplotlib.pyplot as plt
import csv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random

# Function to generate unique user ID
def generate_unique_user_id():
    # Load existing user IDs from the Google Sheet (if any)
    existing_user_ids = load_existing_user_ids()  # You need to implement this function
    
    # Generate a new user ID
    while True:
        new_user_id = str(random.randint(1, 999)).zfill(3)  # Generate a random 3-digit number
        if new_user_id not in existing_user_ids:
            return new_user_id

# Function to load existing user IDs from the Google Sheet
def load_existing_user_ids():
    # Authenticate with Google Sheets API
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)

    # Open the Google Sheet
    sheet = client.open("Data Collection").worksheet("User Details")

    # Get all user IDs from the Google Sheet
    user_ids = sheet.col_values(1)[1:]  # Assuming user IDs are in the first column, excluding the header
    return user_ids

# Function to collect user details
def collect_user_details():
    st.title("User Details")
    st.write("Please fill in the following details:")
    
    # Generate unique user ID
    user_id = generate_unique_user_id()

    name = st.text_input("Name")
    gender = st.selectbox("Gender", ["Male", "Female", "Other"])
    age = st.number_input("Age", min_value=0, max_value=150, step=1)
    city = st.text_input("City")
    state = st.text_input("State")
    nationality = st.text_input("Nationality")
    profession = st.text_input("Profession")

    # Additional column for recording variation
    recording_variation_options = {
        "Silent speech": 1,
        "Mouth open": 2,
        "Lip syncing": 3,
        "Vocalized Speech": 4
    }
    
    recording_variation_text = st.radio(
    "Recording Variation",
    list(recording_variation_options.keys()))
    
    # Map the selected text back to its corresponding numbers
    recording_variation = recording_variation_options[recording_variation_text]


    if st.button("Save Details"):
        # Authenticate with Google Sheets API
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)

        # Open the Google Sheet
        sheet = client.open("Data Collection").worksheet("User Details")

        # Append user details to the Google Sheet
        sheet.append_row([user_id, name, gender, age, city, state, nationality, profession, recording_variation])

        st.success("User details saved successfully!")

# Function to start recording sensor data
def start_recording():
    fs = 250.0  # Sampling rate, Hz
    lowcut = 1.0  # Low cutoff frequency, Hz
    highcut = 100.0  # High cutoff frequency, Hz
    quality_factor = 30.0  # Quality factor for the notch filter

    # Initialize your serial connection
    ser = serial.Serial('COM3', 115200, timeout=1)
    time.sleep(2)  # Wait for the serial connection to initialize

    # Initialize data storage lists for each sensor
    data_a0, data_a2, data_a3, data_a4, data_a5 = [], [], [], [], []

    st.title("Sensor Data Collection")

    # Text input field for the user to enter what they are going to say
    label = st.text_input("Please enter what you are going to say: ")

    st.write("Press the 'Start Recording' button to begin collecting sensor data.")

    if st.button("Start Recording"):
        st.write("Starting readings...")
        start_time = time.time()

        # Collect data for 3 second resulting in 750 points per sensor
        sample_count = 0  # Counter for the number of samples collected
        while sample_count < 750:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').rstrip()
                if "A0:" in line:
                    values = line.split(',')
                    if len(values) >= 5:
                        try:
                            data_a0.append(float(values[0].split(":")[1].strip()))
                            data_a2.append(float(values[1].split(":")[1].strip()))
                            data_a3.append(float(values[2].split(":")[1].strip()))
                            data_a4.append(float(values[3].split(":")[1].strip()))
                            data_a5.append(float(values[4].split(":")[1].strip()))
                            sample_count += 1  # Increment sample_count only on successful parse
                        except (ValueError, IndexError):
                            print(f"Error processing line: {line}")
                            continue
                    else:
                        print(f"Not enough values in line: {line}")
                else:
                    print(f"Line does not contain A0 data: {line}")

        st.success("Data collection completed!")
        st.write("Dimension of data_a0:", len(data_a0))
        st.write("Dimension of data_a2:", len(data_a2))
        st.write("Dimension of data_a3:", len(data_a3))
        st.write("Dimension of data_a4:", len(data_a4))
        st.write("Dimension of data_a5:", len(data_a5))

        ser.close()  # Close the serial connection

        # Process data and plot
        process_and_plot_data(data_a0, data_a2, data_a3, data_a4, data_a5, lowcut, highcut, fs, quality_factor, label)

# Function to process data and plot
def process_and_plot_data(data_a0, data_a2, data_a3, data_a4, data_a5, lowcut, highcut, fs, quality_factor, label):
    # Processing functions
    
    # Generate a Butterworth bandpass filter
    def butter_bandpass(lowcut, highcut, fs, order=4):
        nyq = 0.5 * fs
        low = lowcut / nyq
        high = highcut / nyq
        b, a = butter(order, [low, high], btype='band')
        return b, a
    
    def butter_bandpass_filter(data, lowcut, highcut, fs, order=4):
        b, a = butter_bandpass(lowcut, highcut, fs, order=order)
        y = lfilter(b, a, data)
        return y
    
    # Generate a notch filter
    def design_notch_filter(notch_freq, quality_factor, fs):
        nyq = 0.5 * fs
        freq = notch_freq / nyq
        b, a = iirnotch(freq, quality_factor)
        return b, a

    def apply_notch_filter(data, notch_freq, quality_factor, fs):
        b, a = design_notch_filter(notch_freq, quality_factor, fs)
        y = lfilter(b, a, data)
        return y

    def normalize(data):
        return (data - np.min(data)) / (np.max(data) - np.min(data))

    # Process data_a0
    filtered_a0 = butter_bandpass_filter(data_a0, lowcut, highcut, fs)
    notched_a0_50 = apply_notch_filter(filtered_a0, 50.0, quality_factor, fs)
    notched_a0_60 = apply_notch_filter(notched_a0_50, 60.0, quality_factor, fs)
    normalized_a0 = normalize(notched_a0_60)
    
    # Process data_a2
    filtered_a2 = butter_bandpass_filter(data_a2, lowcut, highcut, fs)
    notched_a2_50 = apply_notch_filter(filtered_a2, 50.0, quality_factor, fs)
    notched_a2_60 = apply_notch_filter(notched_a2_50, 60.0, quality_factor, fs)
    normalized_a2 = normalize(notched_a2_60)
    
    # Process data_a3
    filtered_a3 = butter_bandpass_filter(data_a3, lowcut, highcut, fs)
    notched_a3_50 = apply_notch_filter(filtered_a3, 50.0, quality_factor, fs)
    notched_a3_60 = apply_notch_filter(notched_a3_50, 60.0, quality_factor, fs)
    normalized_a3 = normalize(notched_a3_60)
    
    # Process data_a4
    filtered_a4 = butter_bandpass_filter(data_a4, lowcut, highcut, fs)
    notched_a4_50 = apply_notch_filter(filtered_a4, 50.0, quality_factor, fs)
    notched_a4_60 = apply_notch_filter(notched_a4_50, 60.0, quality_factor, fs)
    normalized_a4 = normalize(notched_a4_60)
    
    # Process data_a5
    filtered_a5 = butter_bandpass_filter(data_a5, lowcut, highcut, fs)
    notched_a5_50 = apply_notch_filter(filtered_a5, 50.0, quality_factor, fs)
    notched_a5_60 = apply_notch_filter(notched_a5_50, 60.0, quality_factor, fs)
    normalized_a5 = normalize(notched_a5_60)

    # Plotting
    fig, axs = plt.subplots(5, 2, figsize=(15, 20))  # 5 rows for sensors, 2 columns for raw and normalized data

    # Helper function to plot data
    def plot_sensor_data(axs, row, raw_data, normalized_data, title):
        axs[row, 0].plot(raw_data)
        axs[row, 0].set_title(f'Raw Data {title}')
        axs[row, 0].set_xlabel('Samples')
        axs[row, 0].set_ylabel('Value')

        axs[row, 1].plot(normalized_data)
        axs[row, 1].set_title(f'Normalized Data {title}')
        axs[row, 1].set_xlabel('Samples')
        axs[row, 1].set_ylabel('Value')

    # Plot data for A0
    plot_sensor_data(axs, 0, data_a0, normalized_a0, 'A0')
    
    # Plot data for A2
    plot_sensor_data(axs, 1, data_a2, normalized_a2, 'A2')
    
    # Plot data for A3
    plot_sensor_data(axs, 2, data_a3, normalized_a3, 'A3')
    
    # Plot data for A4
    plot_sensor_data(axs, 3, data_a4, normalized_a4, 'A4')
    
    # Plot data for A5
    plot_sensor_data(axs, 4, data_a5, normalized_a5, 'A5')

    # Adjust layout and show plot
    plt.tight_layout()
    st.pyplot(fig)

    if st.button("Save recordings"):
            save_recording(data_a0, data_a2, data_a3, data_a4, data_a5, normalized_a0, normalized_a2, normalized_a3, normalized_a4, normalized_a5, label)

def save_recording(data_a0, data_a2, data_a3, data_a4, data_a5, normalized_a0, normalized_a2, normalized_a3, normalized_a4, normalized_a5, label):
    st.write("Saving recordings...")

    scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    
    # Combine all normalized arrays
    raw_combined_data = (
        [round(num, 4) for num in data_a0] +
        [round(num, 4) for num in data_a2] +
        [round(num, 4) for num in data_a3] +
        [round(num, 4) for num in data_a4] +
        [round(num, 4) for num in data_a5]
    )
        
    # Combine all normalized arrays
    normalized_combined_data = (
        [round(num, 4) for num in normalized_a0] +
        [round(num, 4) for num in normalized_a2] +
        [round(num, 4) for num in normalized_a3] +
        [round(num, 4) for num in normalized_a4] +
        [round(num, 4) for num in normalized_a5]
    )
    
    # Get user details
    user_details = st.session_state.user_details
    
    if user_details is not None:
        user_id = user_details[0]  
        recording_variation = user_details[8]  
    else:
        st.error("User details not found.")
        return
    
     # Open the Google Sheet
    raw_sensor_sheet = client.open("Data Collection").worksheet("Raw Sensor Data")
    normalized_sensor_sheet = client.open("Data Collection").worksheet("Normalized Sensor Data")

    # Append raw data to "raw sensor data" worksheet
    raw_sensor_sheet.append_row([user_id, recording_variation] + raw_combined_data)

    # Append normalized data to "normalized sensor data" worksheet
    normalized_sensor_sheet.append_row([user_id, recording_variation] + normalized_combined_data)

    print("Recordings saved successfully!")

# Main function
def main():
    page = st.sidebar.selectbox("Select Page", ["User Details", "Sensor Data Collection"])

    if page == "User Details":
        collect_user_details()
    elif page == "Sensor Data Collection":
        start_recording()

# Entry point
if __name__ == "__main__":
    main()

