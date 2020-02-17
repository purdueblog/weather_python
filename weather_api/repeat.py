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
    slope = 0.149732
    # 매개변수 : time만큼 물줄 경우 , return : 올라가는 soil_moisture
    def up_soil_moisture(self, time):
        return self.slope * time
    
    # 매개변수 : soil_moisture 만큼 올리는대 필요한 시간, return : time  
    def get_time_using_soil_moisture(self, soil_moisture):
        return ( soil_moisture ) / self.slope
    
    # 매개변수 : day, cycle 성장단계에 따른 필요 물량, return : 물양
    def need_water_amount(self, day, cycle = 1):
        return (-0.000025250*(day**3) + 0.003195485*(day**2) + 0.000200062*day +1.143255449) * cycle
    
    # 매개변수 : 주고 싶은 물 양, return: 물양을 주는데 필요한 시간.
    def get_time_using_water(self, water_amount):
        return water_amount / 1.1 
    
    # 매개변수 : time만큼 물을 주면, return: 총 준 물의 양
    def get_amount_using_time(self, time):
    		return time * 1.1
    
    # 매개변수 : 주고 싶은 물 양, return: 물양을 주고 올라가는 soil_moisture
    def get_mad_using_water(self, water_amount):
        return self.up_soil_moisture(self.get_time_using_water(water_amount))
    
    # 매개변수 : 토양수분, return MAD 포인트 
    def convert_soil_moisture_to_MAD(self, soil_moisture):
        if soil_moisture > 16:
            return ((34-16) - soil_moisture) / 34 * 100
        return 100
    
    # 매개변수 : MAD , return mad 값에 따른 수분 토양
    def MAD_convert_to_soilmoisture(self, mad):
        return (18) * (100 - mad) / 100 + 16

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
    

        if(int(times[current_hour]) == 10  and int(times[current_min]) < 30):
            return True
        else:
            return False
    
    def irrigation(self):
        cookies = {'sysauth': '72d61ae1f2c85c702da1e83587e92724'}
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
            limit_moisture = self.MAD_convert_to_soilmoisture(mad)
            if(soil_moisture < limit_moisture):
                
                goal_moisture = self.MAD_convert_to_soilmoisture(0)
                serve_moisture = goal_moisture - soil_moisture

                irr_time = self.get_time_using_soil_moisture(serve_moisture)
                
                irr_time = int(irr_time)
                str_irr_time = str(irr_time)
                print("set time : ", irr_time)

                trigger_request = requests.get('http://192.168.2.241/arduino/irrigation/' + str_irr_time, cookies=cookies)
                print('http://192.168.2.241/arduino/irrigation/' + str_irr_time)
                print(trigger_request, "request ON")

                #insert usage of water to datebase
                amout_of_water = self.get_amount_using_time(irr_time) * 4 
                print("water suffly : ", amout_of_water)
                post = {'water' : amout_of_water, 'dt' : self.full_time}
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
            time.sleep(1800)

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
