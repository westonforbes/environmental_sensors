import os, sys, io
import M5
from M5 import *
import time
from machine import Pin
import dht

rect0 = None
label_temp = None
label_humidity = None
label_status = None
label_debug = None
dht22_sensor = None

def setup():
    global rect0, label_temp, label_humidity, label_status, label_debug, dht22_sensor
    
    M5.begin()
    Widgets.fillScreen(0x222222)
    
    # Header rectangle
    rect0 = Widgets.Rectangle(0, 0, 340, 45, 0xffffff, 0xce4343)
    
    # Title label
    title_label = Widgets.Label("DHT22 Sensor Debug", 100, 15, 1.0, 0xffffff, 0xce4343, Widgets.FONTS.DejaVu18)
    
    # Temperature label
    label_temp = Widgets.Label("Temperature: --°C", 20, 60, 1.0, 0xffffff, 0x222222, Widgets.FONTS.DejaVu18)
    
    # Humidity label  
    label_humidity = Widgets.Label("Humidity: --%", 20, 85, 1.0, 0xffffff, 0x222222, Widgets.FONTS.DejaVu18)
    
    # Status label
    label_status = Widgets.Label("Status: Initializing...", 20, 110, 1.0, 0x00ff00, 0x222222, Widgets.FONTS.DejaVu12)
    
    # Debug label
    label_debug = Widgets.Label("Debug: Starting... (Try 3.3V power)", 20, 135, 1.0, 0xffff00, 0x222222, Widgets.FONTS.DejaVu12)
    
    # Initialize DHT22 sensor on GPIO pin 26 (Port B)
    try:
        dht22_sensor = dht.DHT22(Pin(33))
        label_status.setText("Status: Sensor initialized")
        label_debug.setText("Debug: DHT22 object created")
        print("DHT22 sensor initialized on pin 26")
    except Exception as e:
        label_status.setText("Status: Init Error")
        label_debug.setText(f"Debug: Init error - {str(e)}")
        label_status.setColor(0xff0000, 0x222222)
        print(f"DHT22 initialization error: {e}")

def read_dht22():
    global dht22_sensor, label_temp, label_humidity, label_status, label_debug
    
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
        
        print(f"DHT22 readings - Temp: {temperature}°C, Humidity: {humidity}%")
        
        # Update labels with new readings
        label_temp.setText(f"Temperature: {temperature:.1f}°C")
        label_humidity.setText(f"Humidity: {humidity:.1f}%")
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
    global rect0, label_temp, label_humidity, label_status, read_counter
    
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