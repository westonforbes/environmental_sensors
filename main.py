# Configuration area.#######################################################################

# Sensor Name
SENSOR_NAME = "SENSOR_001"

# Temperature adjustment to known standard.
T_ADJUSTMENT = 0.0

# Humidity adjustment to known standard.
H_ADJUSTMENT = 0.0

# API endpoint.
API_ENDPOINT = "http://www.forbes-server.com:8000/heat_index_data"

############################################################################################


import os, sys, io
import M5
from M5 import *
import time
from machine import Pin
import dht
import math
import network
import requests2
import json

header = None
label_temp = None
label_humidity = None
label_heat_index = None
label_status = None
label_network = None
label_countdown = None
dht22_sensor = None
label_t_adjustment = None
label_h_adjustment = None

# We use counters to stagger delays, this is so the delays are non-blocking and we
# dont have to get fancy with multithreading. Each cycle is approximately 300 ms.
sensor_counter = 0
post_counter = 0
post_interval = 33 # Approximately 10 seconds.
sensor_interval = 10 # Approximately 3 seconds.



# Store last successful readings for POST.
last_temp_f = None
last_humidity = None
last_heat_index = None

def setup_graphics():

    # Setup global connections.
    global header, label_temp, label_humidity, label_heat_index, label_status, label_t_adjustment, label_h_adjustment, label_network, label_countdown

    # Fill the screen one color.
    Widgets.fillScreen(0x222222)
    
    # Create header rectangle.
    header = Widgets.Rectangle(0, 0, 340, 35, 0xce4343, 0xce4343)
    
    # Create title label.
    title_label = Widgets.Label("Environmental Sensor", 10, 10, 1.0, 0xffffff, 0xce4343, Widgets.FONTS.DejaVu18)
    
    # Create temperature label.
    label_temp = Widgets.Label("Temperature: -- F", 10, 50, 1.0, 0xffffff, 0x222222, Widgets.FONTS.DejaVu12)

    # Create t_adjust label.
    label_t_adjustment = Widgets.Label("Temperature Adjustment: {T_ADJUSTMENT:0.1f} F", 10, 70, 1.0, 0xffffff, 0x222222, Widgets.FONTS.DejaVu12)
    
    # Create humidity label.
    label_humidity = Widgets.Label("Humidity: -- %", 10, 90, 1.0, 0xffffff, 0x222222, Widgets.FONTS.DejaVu12)

    # Create h_adjust label.
    label_h_adjustment = Widgets.Label(f"Humidity Adjustment: {H_ADJUSTMENT:0.1f} %", 10, 110, 1.0, 0xffffff, 0x222222, Widgets.FONTS.DejaVu12)
    
    # Create heat index label.
    label_heat_index = Widgets.Label("Heat Index: -- F", 10, 130, 1.0, 0xff8800, 0x222222, Widgets.FONTS.DejaVu12)
    
    # Create network status label.
    label_network = Widgets.Label("Network: Connecting...", 10, 170, 1.0, 0x00ffff, 0x222222, Widgets.FONTS.DejaVu12)
    
    # Create countdown label.
    label_countdown = Widgets.Label("Next POST: --s", 10, 190, 1.0, 0xffff00, 0x222222, Widgets.FONTS.DejaVu12)
    
    # Create status label.
    label_status = Widgets.Label("Status: Starting...", 10, 215, 1.0, 0xffff00, 0x222222, Widgets.FONTS.DejaVu12)


def setup_network():
    """Check existing network connection status"""
    global label_network
    
    try:
        # Get existing WiFi connection (managed by OS)
        wlan = network.WLAN(network.STA_IF)
        
        if wlan.isconnected():
            ip = wlan.ifconfig()[0]
            label_network.setText(f"Network: Connected - {ip}")
            label_network.setColor(0x00ff00, 0x222222)
            return wlan
        else:
            label_network.setText("Network: Not connected")
            label_network.setColor(0xff0000, 0x222222)
            return None
            
    except Exception as e:
        label_network.setText(f"Network: Error - {str(e)[:20]}")
        label_network.setColor(0xff0000, 0x222222)
        return None


def setup_sensor():

    # Set up global connections.
    global label_status, dht22_sensor
    
    # Initialize DHT22 sensor on GPIO pin 33 (Port A).
    try:
        dht22_sensor = dht.DHT22(Pin(33))
        label_status.setText("Status: Sensor initialized.")
    except Exception as e:
        label_status.setText(f"Init error - {str(e)}")


def calculate_heat_index(temp_f, humidity):
    
    # Simple formula for initial calculation.
    simple_hi = 0.5 * (temp_f + 61.0 + ((temp_f - 68.0) * 1.2) + (humidity * 0.094))
    
    # Average with temperature.
    simple_avg = (simple_hi + temp_f) / 2.0
    
    # If result is less than 80°F, use simple formula.
    if simple_avg < 80.0:
        return simple_avg
    
    # Use full Rothfusz regression for higher temperatures.
    T = temp_f
    RH = humidity
    
    HI = (-42.379 + 
          2.04901523 * T + 
          10.14333127 * RH - 
          0.22475541 * T * RH - 
          0.00683783 * T * T - 
          0.05481717 * RH * RH + 
          0.00122874 * T * T * RH + 
          0.00085282 * T * RH * RH - 
          0.00000199 * T * T * RH * RH)
    
    # Apply adjustments based on conditions.
    
    # Adjustment for low humidity (RH < 13%) and temp between 80-112°F.
    if RH < 13 and 80 <= T <= 112:
        adjustment = ((13 - RH) / 4) * math.sqrt((17 - abs(T - 95)) / 17)
        HI -= adjustment
    
    # Adjustment for high humidity (RH > 85%) and temp between 80-87°F  .
    elif RH > 85 and 80 <= T <= 87:
        adjustment = ((RH - 85) / 10) * ((87 - T) / 5)
        HI += adjustment
    
    return HI


def get_heat_index_description(heat_index_f):

    if heat_index_f < 80:
        return "Normal", 0x00ff00  # Green
    elif heat_index_f < 90:
        return "Caution", 0xffff00  # Yellow
    elif heat_index_f < 105:
        return "Extreme Caution", 0xff8800  # Orange
    elif heat_index_f < 130:
        return "Danger", 0xff0000  # Red
    else:
        return "Extreme Danger", 0x800080  # Purple


def post_sensor_data(temp_f, humidity, heat_index_f):
    """POST sensor data to the API endpoint using requests2"""
    global label_network
    
    try:
        # Prepare the data payload
        payload = {
            "name": SENSOR_NAME,
            "temperature_f": round(temp_f, 1),
            "temperature_f_offset": round(T_ADJUSTMENT, 1),
            "humidity_percentage": round(humidity, 1),
            "humidity_percentage_offset": round(H_ADJUSTMENT, 1),
            "heat_index_f": round(heat_index_f, 1)
        }
        
        # Set headers
        headers = {
            "Content-Type": "application/json"
        }
        
        # Update network status to show posting
        label_network.setText("Network: Posting data...")
        label_network.setColor(0x00ffff, 0x222222)
        
        # Make the POST request using requests2
        response = requests2.post(
            API_ENDPOINT,
            json=payload,
            headers=headers
        )
        
        # Check response status
        if response.status_code == 200:
            label_network.setText(f"Network: POST OK ({response.status_code})")
            label_network.setColor(0x00ff00, 0x222222)
        else:
            label_network.setText(f"Network: POST Error {response.status_code}")
            label_network.setColor(0xff8800, 0x222222)
        
        # Close the response
        response.close()
        
    except Exception as e:
        error_msg = str(e)[:20]  # Truncate long error messages
        label_network.setText(f"Network: POST Fail - {error_msg}")
        label_network.setColor(0xff0000, 0x222222)


def read_dht22():

    # Set up global connections.
    global dht22_sensor, label_temp, label_humidity, label_heat_index, label_status, label_t_adjustment, label_h_adjustment
    global last_temp_f, last_humidity, last_heat_index
    
    # Check if the sensor is not initialized...
    if dht22_sensor is None:
        
        # Notify.
        label_status.setText("Status: Sensor not initialized.")
        return None, None, None
    
    # Try protect...
    try:

        # Notify.
        label_status.setText("Status: Attempting to read sensor...")
        
        # Trigger measurement.
        dht22_sensor.measure()
        
        # Read temperature and humidity.
        temp_c = dht22_sensor.temperature()
        humidity = dht22_sensor.humidity()
        
        # Convert to f.
        temp_f = (temp_c * 9.0 / 5.0) + 32.0

        # Add adjustments.
        temp_f = temp_f + T_ADJUSTMENT
        humidity = humidity + H_ADJUSTMENT

        # Calculate heat index.
        heat_index_f = calculate_heat_index(temp_f, humidity)

        # Store last successful readings
        last_temp_f = temp_f
        last_humidity = humidity
        last_heat_index = heat_index_f

        # Get heat index description and color.
        hi_description, hi_color = get_heat_index_description(heat_index_f)
        
        # Update labels with new readings.
        label_temp.setText(f"Temperature: {temp_f:.1f} F")
        label_t_adjustment.setText(f"Temperature Adjustment: {T_ADJUSTMENT:.1f} F")
        label_humidity.setText(f"Humidity: {humidity:.1f} %")
        label_h_adjustment.setText(f"Humidity Adjustment: {H_ADJUSTMENT:.1f} %")
        label_heat_index.setText(f"Heat Index: {heat_index_f:.1f} F ({hi_description})")
        label_heat_index.setColor(hi_color, 0x222222)
        
        # Notify.
        label_status.setText("Status: Read successful")
        label_status.setColor(0x00ff00, 0x222222)
        
        return temp_f, humidity, heat_index_f
        
    except OSError as e:
        
        # Handle sensor read errors.
        error_msg = f"OSError: {e}"
        label_temp.setText("Temperature: --")
        label_humidity.setText("Humidity: --") 
        label_status.setText(f"OSError: {error_msg}")
        label_status.setColor(0xff0000, 0x222222)
        return None, None, None
    
    except Exception as e:
        
        # Handle other errors.
        error_msg = f"Error: {str(e)}"
        label_temp.setText("Temperature: --")
        label_humidity.setText("Humidity: --") 
        label_status.setText(f"Exception: {error_msg}")
        label_status.setColor(0xff0000, 0x222222)
        return None, None, None


def loop():

    # Set up global connections.
    global sensor_counter, post_counter, last_temp_f, last_humidity, last_heat_index, label_countdown
    
    # Update the core library.
    M5.update()
    
    # Only read every 10 loops (about 3 seconds with 300ms delay).
    if sensor_counter >= sensor_interval:
        temp_f, humidity, heat_index = read_dht22()
        sensor_counter = 0
    else:
        sensor_counter += 1
    
    # Update countdown display
    seconds_until_post = int((post_interval - post_counter) * 0.3)  # 0.3 seconds per loop
    if seconds_until_post > 0:
        label_countdown.setText(f"Next POST: {seconds_until_post}s")
        label_countdown.setColor(0xffff00, 0x222222)
    else:
        label_countdown.setText("Next POST: Now!")
        label_countdown.setColor(0x00ff00, 0x222222)
    
    # POST data every post_interval loops (about 30 seconds)
    post_counter += 1
    if post_counter >= post_interval:
        if last_temp_f is not None and last_humidity is not None and last_heat_index is not None:
            post_sensor_data(last_temp_f, last_humidity, last_heat_index)
        post_counter = 0
    
    # Short delay (allow us to refresh the ui).
    time.sleep(0.3)


if __name__ == '__main__':
    
    # Try protect...
    try:
        # Setup the graphics.
        setup_graphics()

        # Setup network connection check
        wlan = setup_network()

        # Setup the sensor.
        setup_sensor()

        # Primary loop.
        while True:
            loop()

    # Catch any issues...  
    except (Exception, KeyboardInterrupt) as e:
        try:
            from utility import print_error_msg
            print_error_msg(e)
        except ImportError:
            print("please update to latest firmware")