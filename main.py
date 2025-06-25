import os, sys, io
import M5
from M5 import *
import time
from machine import Pin
import dht

rect0 = None
label_temp = None
label_humidity = None
label_heat_index = None
label_status = None
label_debug = None
dht22_sensor = None

def setup():
    global rect0, label_temp, label_humidity, label_heat_index, label_status, label_debug, dht22_sensor
    
    M5.begin()
    Widgets.fillScreen(0x222222)
    
    # Header rectangle
    rect0 = Widgets.Rectangle(0, 0, 340, 45, 0xffffff, 0xce4343)
    
    # Title label
    title_label = Widgets.Label("DHT22 Sensor Debug", 100, 15, 1.0, 0xffffff, 0xce4343, Widgets.FONTS.DejaVu18)
    
    # Temperature label
    label_temp = Widgets.Label("Temperature: --C", 20, 60, 1.0, 0xffffff, 0x222222, Widgets.FONTS.DejaVu18)
    
    # Humidity label  
    label_humidity = Widgets.Label("Humidity: --%", 20, 85, 1.0, 0xffffff, 0x222222, Widgets.FONTS.DejaVu18)
    
    # Heat Index label
    label_heat_index = Widgets.Label("Heat Index: --F", 20, 110, 1.0, 0xff8800, 0x222222, Widgets.FONTS.DejaVu18)
    
    # Status label
    label_status = Widgets.Label("Status: Initializing...", 20, 135, 1.0, 0x00ff00, 0x222222, Widgets.FONTS.DejaVu12)
    
    # Debug label
    label_debug = Widgets.Label("Debug: Starting... (Try 3.3V power)", 20, 160, 1.0, 0xffff00, 0x222222, Widgets.FONTS.DejaVu12)
    
    # Initialize DHT22 sensor on GPIO pin 33 (Port A)
    try:
        dht22_sensor = dht.DHT22(Pin(33))
        label_status.setText("Status: Sensor initialized")
        label_debug.setText("Debug: DHT22 object created")
        print("DHT22 sensor initialized on pin 33")
    except Exception as e:
        label_status.setText("Status: Init Error")
        label_debug.setText(f"Debug: Init error - {str(e)}")
        label_status.setColor(0xff0000, 0x222222)
        print(f"DHT22 initialization error: {e}")

def celsius_to_fahrenheit(celsius):
    """Convert Celsius to Fahrenheit"""
    return (celsius * 9.0 / 5.0) + 32.0

def calculate_heat_index(temp_f, humidity):
    """
    Calculate heat index using NOAA formula
    temp_f: temperature in Fahrenheit
    humidity: relative humidity in percent
    Returns heat index in Fahrenheit
    """
    import math
    
    # Simple formula for initial calculation
    simple_hi = 0.5 * (temp_f + 61.0 + ((temp_f - 68.0) * 1.2) + (humidity * 0.094))
    
    # Average with temperature
    simple_avg = (simple_hi + temp_f) / 2.0
    
    # If result is less than 80°F, use simple formula
    if simple_avg < 80.0:
        return simple_avg
    
    # Use full Rothfusz regression for higher temperatures
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
    
    # Apply adjustments based on conditions
    
    # Adjustment for low humidity (RH < 13%) and temp between 80-112°F
    if RH < 13 and 80 <= T <= 112:
        adjustment = ((13 - RH) / 4) * math.sqrt((17 - abs(T - 95)) / 17)
        HI -= adjustment
    
    # Adjustment for high humidity (RH > 85%) and temp between 80-87°F  
    elif RH > 85 and 80 <= T <= 87:
        adjustment = ((RH - 85) / 10) * ((87 - T) / 5)
        HI += adjustment
    
    return HI

def get_heat_index_description(heat_index_f):
    """Return heat index category and color"""
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

def read_dht22():
    global dht22_sensor, label_temp, label_humidity, label_heat_index, label_status, label_debug
    
    if dht22_sensor is None:
        label_debug.setText("Debug: Sensor not initialized")
        return None, None
    
    try:
        label_debug.setText("Debug: Calling measure()...")
        print("Attempting to read DHT22...")
        
        # Trigger measurement
        dht22_sensor.measure()
        
        label_debug.setText("Debug: Getting values...")
        
        # Read temperature and humidity
        temperature = dht22_sensor.temperature()
        humidity = dht22_sensor.humidity()
        
        # Calculate heat index
        temp_f = celsius_to_fahrenheit(temperature)
        heat_index_f = calculate_heat_index(temp_f, humidity)
        heat_index_c = (heat_index_f - 32.0) * 5.0 / 9.0
        
        # Get heat index description and color
        hi_description, hi_color = get_heat_index_description(heat_index_f)
        
        print(f"DHT22 readings - Temp: {temperature}C ({temp_f:.1f}F), Humidity: {humidity}%")
        print(f"Heat Index: {heat_index_f:.1f}F - {hi_description}")
        
        # Update labels with new readings
        label_temp.setText(f"Temperature: {temperature:.1f}C")
        label_humidity.setText(f"Humidity: {humidity:.1f}%")
        label_heat_index.setText(f"Heat Index: {heat_index_f:.1f}F ({hi_description})")
        label_heat_index.setColor(hi_color, 0x222222)
        
        label_status.setText("Status: Reading OK")
        label_status.setColor(0x00ff00, 0x222222)
        label_debug.setText("Debug: Read successful")
        
        return temperature, humidity
        
    except OSError as e:
        # Handle sensor read errors
        error_msg = f"OSError: {e}"
        print(f"DHT22 OSError: {e}")
        label_temp.setText("Temperature: Read Error")
        label_humidity.setText("Humidity: Read Error") 
        label_status.setText("Status: OSError")
        label_status.setColor(0xff0000, 0x222222)
        label_debug.setText(f"Debug: {error_msg}")
        return None, None
    
    except Exception as e:
        # Handle other errors
        error_msg = f"Error: {str(e)}"
        print(f"DHT22 Error: {e}")
        label_status.setText("Status: Exception")
        label_status.setColor(0xff0000, 0x222222)
        label_debug.setText(f"Debug: {error_msg}")
        return None, None

# Counter for timing
read_counter = 0

def loop():
    global rect0, label_temp, label_humidity, label_heat_index, label_status, read_counter
    
    M5.update()
    
    # Only read every 10 loops (about 3 seconds with 300ms delay)
    if read_counter >= 10:
        read_dht22()
        read_counter = 0
    else:
        read_counter += 1
    
    # Shorter delay for UI responsiveness
    time.sleep(0.3)

if __name__ == '__main__':
    try:
        setup()
        while True:
            loop()
    except (Exception, KeyboardInterrupt) as e:
        try:
            from utility import print_error_msg
            print_error_msg(e)
        except ImportError:
            print("please update to latest firmware")