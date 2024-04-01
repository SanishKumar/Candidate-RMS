import json
logjson = """{
    "student":["status",{"applied_on":"date"}],
    "base_hr":{
        "open1":["username","date","status","review",{"viewed_on":"date","meeting_on":"date","meeting_mail":["status","date"],"forward_status":["teamleadname","date"],"forward_members":["team_member1","team_member2"]
        }],
        "open2":["username","date","status","review","reopendate",{"viewed_on":"date","meeting_on":"date","meeting_mail":["status","date"],"forward_status":["teamleadname","date"],"forward_members":["team_member1","team_member2"]
        }]
    },
    "team_lead":{
        "open1":["username","date","status","review",{"team_member1":["joined","username","status","review"],"team_member2":["not_joined","username","status","review"],"forward_status":["managername","date"]}]
    },
    "manager":{
        "open1":["username","date","status","review","with_meeting",{"meeting_on":"date","meeting_mail":["status","date"],"forward_status":["mainhrname","date"]},{"manager1":["joined","username","status","review"],"manager2":["not_joined","username","status","review"]}]
    },
    "mainhr":{
        "open1":["username","date","status","review","with_meeting",{"meeting_on":"date","meeting_mail":["status","date"],"congratulations_mail":["status","date"],"forward_status":["basehrname","date"]},{"mainhr1":["joined","username","status","review"],"mainhr2":["not_joined","username","status","review"]}]
    }
}"""

data = json.loads(logjson)
data['base_hr']['open1'][0] = 'new'
data['base_hr']['open1'][1] = 'ne'
data['base_hr']['open1'][2] = 'n'
data['base_hr']['open1'][3] = 'new'
data['base_hr']['open1'][4]['viewed_on'] = str('new')
data['base_hr']['open1'][4]['meeting_mail'][1] = str('new')

print(data['base_hr'])


for i in [3, 3, 3]:
    l = i
print(l)