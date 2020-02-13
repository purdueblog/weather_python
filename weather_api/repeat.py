import time 
from threading import Thread
import requests
from pymongo import MongoClient
from pprint import pprint
from weather_api.api_id import api_id
import datetime
import isodate

class sensor_worker(Thread):
    full_time = ""
    def check_hour(self):
        time_api_url = 'http://worldtimeapi.org/api/timezone/America/Indiana/Indianapolis'
        time_request = requests.get(time_api_url).json()
        self.full_time = time_request['datetime']
        current_time = self.full_time[11:19]
        times = current_time.split(':')
        current_hour = 0
        current_min = 1

        print("hour : " + times[current_hour])
        print("min : " + times[current_min])
        
        return True

        if(int(times[current_hour]) == 9 and int(times[current_min]) < 30):
            return True
        else:
            return False
    
    def irrigation(self):
        cookies = {'sysauth': '87f2cda04e005dc61b8d5c8d81cadb5f'}
        lora_url = 'https://api.thingspeak.com/channels/970723/feeds.json?api_key=AU0TNWBNLRYXU1QL&results=5'
        lora_request = requests.get(lora_url).json()
        datas = lora_request["feeds"]
        data = datas[len(datas) - 1]
            
        field1 =  data["field1"]
        field2 =  data["field2"]
        field3 =  data["field3"]

        cluster = MongoClient("mongodb+srv://myungwoo:didhk7339@cluster0-hrdwg.mongodb.net/test?retryWrites=true&w=majority")
        db = cluster["irrigation"]
        collection = db["irrigation"]
       
        soil_moisture = float(field3)
        if(self.check_hour()):
            print("soil_moisture : ", soil_moisture)
            mad = 30
            if(soil_moisture < mad):
                depth = 1.0
                awc = 0.21
                net_irr = awc * mad
                efficiency_of_drip = 80.0
                
                ga = net_irr / efficiency_of_drip

                area = 0.11
                flow_rate = 0.8

                # time을 분으로 환산
                irr_time = int(((ga * area) / (1.6 * flow_rate)) * 3600)

                str_irr_time = "0"
                
                print("set time : ", irr_time)

                trigger_request = requests.get('http://192.168.2.241/arduino/irrigation/' + str_irr_time, cookies=cookies)
                print('http://192.168.2.241/arduino/irrigation/' + str_irr_time)
                print(trigger_request, "request ON")

                #insert usage of water to datebase
                print("time : ", self.full_time)
                post = {'water' : 100, 'dt' : self.full_time}
                insert_id = collection.insert_one(post).inserted_id
                print("Irrigation data Inserted !! " , insert_id)
                print("\n")
                
        else:
            trigger_request = requests.get('http://192.168.2.241/arduino/irrigation/0', cookies=cookies)
            print("soil_moisture : ", soil_moisture)
            print(trigger_request, "request OFF")
            print("\n")
    def run(self):
        while(True):
            self.irrigation()
            time.sleep(30)

class weather_worker(Thread):
    def run(self):
        # connect to weather collection
        cluster = MongoClient("mongodb+srv://myungwoo:didhk7339@cluster0-hrdwg.mongodb.net/test?retryWrites=true&w=majority")
        db = cluster["weather"]
        collection = db["weather"]

        while(True):
            weather_url = 'https://api.openweathermap.org/data/2.5/weather?q={},us&appid={}'
            city = 'Lafayette '
            weatehr_request = requests.get(weather_url.format(city, api_id)).json()
           # check it is rain
            if 'rain' not in weatehr_request:
                print("not rain")
            else:
                print("It's rain")
                rainfall = weatehr_request['rain']['1h']

                time_api_url = 'http://worldtimeapi.org/api/timezone/America/Indiana/Indianapolis'
                time_request = requests.get(time_api_url).json()
                full_time = time_request['datetime']
            
                current_isodate = isodate.parse_datetime(full_time)
                post = {'rainfall' : rainfall, 'dt' : current_isodate}
                new_id = collection.insert_one(post).inserted_id
                print("Rain data inserted!!  ", new_id)

            time.sleep(3600)

def one_time_startup():
    sensor_worker().start()
    weather_worker().start()
