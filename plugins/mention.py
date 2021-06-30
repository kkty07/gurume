# coding: utf-8

import json
import sys
import re
import sqlite3
from typing import Pattern, Text
from numpy import empty, generic, savez_compressed, select, string_
from pandas.core.algorithms import diff
from pandas.core.frame import DataFrame
import requests
import pandas as pd
import datetime
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


from slackbot.bot import respond_to     # @botname: で反応するデコーダ
from slackbot.bot import listen_to      # チャネル内発言で反応するデコーダ
from slackbot.bot import default_reply  # 該当する応答がない場合に反応するデコーダ
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# @respond_to('string')     bot宛のメッセージ
#                           stringは正規表現が可能 「r'string'」
# @listen_to('string')      チャンネル内のbot宛以外の投稿
#                           @botname: では反応しないことに注意
#                           他の人へのメンションでは反応する
#                           正規表現可能
# @default_reply()          DEFAULT_REPLY と同じ働き
#                           正規表現を指定すると、他のデコーダにヒットせず、
#                           正規表現にマッチするときに反応
#                           ・・・なのだが、正規表現を指定するとエラーになる？

# message.reply('string')   @発言者名: string でメッセージを送信
# message.send('string')    string を送信
# message.react('icon_emoji')  発言者のメッセージにリアクション(スタンプ)する
#                               文字列中に':'はいらない

slack_token ='' #slackbotのトークン
client = WebClient(token=slack_token)
con = sqlite3.connect("gurume.db",check_same_thread=False,isolation_level=None)
cur=con.cursor()
#executeはsqlコマンドを実行するためのメソッド
#sqlのテーブル作成を行う
#varchar100：100文字まで記入できるという意味, INTEGER PRIMARY KEY制約が設定されるとすでに存在するデータと同じ値を持つデータを追加することが出来ない
#AUTOINCREMENTは指定したカラム (フィールド)に対してデータが追加されると、MySQLが一意の値を自動的に付与する機能

cur.execute('''CREATE TABLE IF NOT EXISTS food_gurume (id INTEGER PRIMARY KEY AUTOINCREMENT,shop_name varchar(100),keyword varchar(100),price varchar DEFAULT '/',
word varchar DEFAULT '記載なし',hotpepperapi varchar(10000),genre varchar(100),photo varchar(10000),access varchar(1000),score integer DEFAULT 0)''')
#id INTEGER PRIMARY KEY AUTOINCREMENT
#food_gurumeという名前の表から全データを選択
# cur.execute("SELECT * FROM food_gurume")
# (select * from food_gurume where rowid = last_insert_rowid())
# # cur.execute("SELECT LAST_INSERT_ROWID()")
# df = pd.DataFrame(cur.fetchall())  # 上でinsertした行をリスト化しdfへ格納
# id = df.iat[0, 0]  # 上のdfをiatの0.0に入れてそれがid

#str:文字列に変換して表示　fetchall：結果セットに残っている全ての行を含む配列を返す
print("初期状態" + str(cur.fetchall()))

#登録の記入方法を表示
# @listen_to(r'^登録方法$')
# @respond_to(r'^登録方法$')
# def mention_func(message):
#     message.reply('[登録　店名　キーワード　価格　時間　一言]の順番で記入してください')

#ｒは文字列　^文字の先頭、\s空白、.*なんでも登録する、＄文字の終わり
#print:画面に出力する構文　@respond_to:メンション(@でターゲット指定)した場合のみ応答を返す @listen_toはメンションをしなくても応答を返す
@listen_to(r'^登録\s(.*)$')
@respond_to(r'^登録\s(.*)$')#登録がmessageに入って、登録の後に記入された文字がtextに入る
def add(message,text):
    text_list = re.split('\s+', text)
    if len(text_list)>=5:
        message.reply('再入力してください')
    else:
        message.react('+1') #スタンプのリアクションを返す
        text_list = re.split('\s+', text) #空白でテキスト分けて(split)text_listに=代入する
        if len(text_list)==4:
            shop_name = text_list[0] #shop_nameという変数にtext_list[0](店名)を=代入する
            keyword = text_list[1]
            price = text_list[2]
            word = text_list[3]
            result_url,result_genre,result_name,result_photo,result_access=hotpepperapi(shop_name,keyword,message)
            cur.execute("select * from food_gurume where hotpepperapi=?",[result_url])
            df = pd.DataFrame(cur.fetchall())
            if df.shape[0]>=1: 
                message.reply('すでに存在しています')#0:縦の長さを指定 .shapeで大きさをとれる（もしdfにデータが１つ以上あるなら表示、無いなら存在しないと表示）
            else:
                cur.execute("INSERT INTO food_gurume(shop_name,keyword,price,word,hotpepperapi,genre,photo,access)VALUES (?,?,?,?,?,?,?,?)",
                            [str(result_name),keyword,price,word,str(result_url),str(result_genre),str(result_photo),str(result_access)])
                cur.execute("select * from food_gurume where rowid = last_insert_rowid()")
                # cur.execute("SELECT LAST_INSERT_ROWID()")
                df = pd.DataFrame(cur.fetchall())  # 上でinsertした行をリスト化しdfへ格納
                id = df.iat[0, 0]  # 上のdfをiatの0.0に入れてそれがid
                for index, row in df.iterrows():
                    slack_display(message,str(row[1]),str(row[5]),str(row[6]),str(row[3]),str(row[8]),str(row[4]),str(row[7]),str(row[0]),row[9]) #row:行、#column:列
                    message.reply('評価が付けられます。５段階評価を入力してください　「評価　ID番号 1~5」\n\n') 


        elif len(text_list)==1:
            shop_name = text_list[0]
            # cur.execute("INSERT INTO food_gurume(shop_name)VALUES (?)",[shop_name])
            message.reply('店名　店舗名　まで入力してください')
        elif len(text_list)==2:
            shop_name = text_list[0]
            keyword = text_list[1]
            result_url,result_genre,result_name,result_photo,result_access=hotpepperapi(shop_name,keyword,message)
            cur.execute("select * from food_gurume where hotpepperapi=?",[result_url])
            df = pd.DataFrame(cur.fetchall())
            if df.shape[0]>=1: 
                message.reply('すでに存在しています')#0:縦の長さを指定 .shapeで大きさをとれる（もしdfにデータが１つ以上あるなら表示、無いなら存在しないと表示）
            else:
                cur.execute("INSERT INTO food_gurume(shop_name,keyword,hotpepperapi,genre,photo,access)VALUES (?,?,?,?,?,?)",[str(result_name),keyword,str(result_url),str(result_genre),str(result_photo),str(result_access)])

                cur.execute("select * from food_gurume where rowid = last_insert_rowid()")
                # cur.execute("SELECT LAST_INSERT_ROWID()")
                df = pd.DataFrame(cur.fetchall())  # 上でinsertした行をリスト化しdfへ格納
                id = df.iat[0, 0]  # 上のdfをiatの0.0に入れてそれがid
                for index, row in df.iterrows():
                    slack_display(message,str(row[1]),str(row[5]),str(row[6]),str(row[3]),str(row[8]),str(row[4]),str(row[7]),str(row[0]),row[9]) #row:行、#column:列
                    message.reply('評価が付けられます。５段階評価を入力してください　「評価　ID番号 1~5」\n\n') 

            # message.reply('登録完了 '+str(result_name)+' '+str(result_url)+'\n\n ５段階評価を入力してください　「評価　ID番号 1~5」\n\n')
        elif len(text_list)==3:
            shop_name = text_list[0]
            keyword = text_list[1]
            price = text_list[2]
            result_url,result_genre,result_name,result_photo,result_access=hotpepperapi(shop_name,keyword,message)
            cur.execute("select * from food_gurume where hotpepperapi=?",[result_url])
            df = pd.DataFrame(cur.fetchall())
            if df.shape[0]>=1: 
                message.reply('すでに存在しています')#0:縦の長さを指定 .shapeで大きさをとれる（もしdfにデータが１つ以上あるなら表示、無いなら存在しないと表示）
            else:
                cur.execute("INSERT INTO food_gurume(shop_name,keyword,price,hotpepperapi,genre,photo,access)VALUES (?,?,?,?,?,?,?)",[str(result_name),keyword,price,str(result_url),str(result_genre),str(result_photo),str(result_access)])
                cur.execute("select * from food_gurume where rowid = last_insert_rowid()")
                # cur.execute("SELECT LAST_INSERT_ROWID()")
                df = pd.DataFrame(cur.fetchall())  # 上でinsertした行をリスト化しdfへ格納
                id = df.iat[0, 0]  # 上のdfをiatの0.0に入れてそれがid
                for index, row in df.iterrows():
                    slack_display(message,str(row[1]),str(row[5]),str(row[6]),str(row[3]),str(row[8]),str(row[4]),str(row[7]),str(row[0]),row[9]) #row:行、#column:列
                    message.reply('評価が付けられます。５段階評価を入力してください　「評価　ID番号 1~5」\n\n') 

def slack_display(message,shop_name,result_url,result_genre,price,result_access,word,result_photo,id,score):
    try:
        if result_url!="urlがみつかりません":
            result_url="*<"+result_url+"|"+shop_name+">*\n"
        else:
            result_url="*"+shop_name+"*"

        if result_photo=="なし":
            result_photo=""
        else:
            result_photo=result_photo


        response = client.chat_postMessage(
            channel="{}".format(message.body["channel"]),
            text="test",
            as_user=True,
            blocks=[
                {
                    "type":"divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": result_url+"\n"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": "*[ID]*\n"+id+"\n"
                        },
                        {
                            "type": "mrkdwn",
                            "text": "*[評価]*\n"+":star:"* score+"\n"
                        },
                        {
                            "type": "mrkdwn",
                            "text": "*[価格]*\n"+price+"円"
                        },
                        {
                            "type": "mrkdwn",
                            "text": "*[ジャンル]*\n"+result_genre+"\n"
                        },
                        {
                            "type": "mrkdwn",
                            "text": "*[アクセス]*\n"+result_access+"\n"
                        },
                        {
                            "type": "mrkdwn",
                            "text": "*[コメント]*\n"+word+"\n"
                        }
                    ],
                    "accessory": {
                        "type": "image",
                        "image_url": result_photo,
                        "alt_text": "image"
                    }
                }
            ]
         )
    except SlackApiError as e:
        assert e.response["error"] 

@listen_to(r'^全て表示$')
@respond_to(r'^全て表示$')
def display(message):
    cur.execute("select * from food_gurume")
    df = pd.DataFrame(cur.fetchall())
    for index, row in df.iterrows():
        slack_display(message,str(row[1]),str(row[5]),str(row[6]),str(row[3]),str(row[8]),str(row[4]),str(row[7]),str(row[0]),row[9]) #row:行、#column:列

@listen_to(r'^評価\s(.*)$')
@respond_to(r'^評価\s(.*)$')#登録がmessageに入って、登録の後に記入された文字がtextに入る
def add(message,text):
    text=str(text)
    text_list = re.split('\s+', text)
    if text_list[0].isascii() and text_list[0].isdecimal() and text_list[1].isascii() and text_list[1].isdecimal():

        message.react('+1') #スタンプのリアクションを返す
        text_list = re.split('\s+', text) #空白でテキスト分けて(split)text_listに=代入する
        if len(text_list)!=2:
            message.reply('評価　ID　1~5 と記入してください')
            return
        id = text_list[0] #shop_nameという変数にtext_list[0](店名)を=代入する
        score = text_list[1]
        if int(score)>=6:
                message.reply('5以下で入力してください')
        else:
                cur.execute("update food_gurume set score=? where id=?",[score,id])
                message.reply('評価'+score+'で登録しました')
    # elif text_list>=3:
    #     message.reply('「評価　ID番号　1~5」と正しく入力してください')    
    else:
        message.reply('半角整数(１～５)で正しく入力してください')
        
        if len(text_list)>=4:
                message.reply('再入力してください')

@listen_to(r'^ランキング$')
@respond_to(r'^ランキング$')
def display(message):
    cur.execute("select * from food_gurume where score >=1 order by score asc")
    df = pd.DataFrame(cur.fetchall())
    for index, row in df.iterrows():
        slack_display(message,str(row[1]),str(row[5]),str(row[6]),str(row[3]),str(row[8]),str(row[4]),str(row[7]),str(row[0]),row[9]) #row:行、#column:列


#ジャンルで検索可能
@listen_to(r'^ジャンル\s(.*)$')
@respond_to(r'^ジャンル\s(.*)$')
def display2(message,text):
    genre=text
    text_list=["居酒屋", "ダイニングバー・バル", "創作料理", "和食", "洋食", "イタリアン・フレンチ", "中華", "焼肉・ホルモン", "韓国料理", "アジア・エスニック料理", "各国料理", "ラーメン", "お好み焼き・もんじゃ", "カフェ・スイーツ","バー・カクテル", "カラオケ・パーティー", "その他グルメ"]
    if genre not in text_list:
        message.reply('''ジャンル検索は以下から選択し、記入してください\n
        【居酒屋, ダイニングバー・バル, 創作料理, 和食, 洋食, イタリアン・フレンチ, 中華, 焼肉・ホルモン,
　       韓国料理, アジア・エスニック料理, 各国料理, ラーメン, お好み焼き・もんじゃ, カフェ・スイーツ,
            バー・カクテル, カラオケ・パーティー, その他グルメ】''')
        return
    cur.execute("select * from food_gurume where genre=?",[genre])
    df = pd.DataFrame(cur.fetchall())
    if df.shape[0]>=1: #0:縦の長さを指定 .shapeで大きさをとれる（もしdfにデータが１つ以上あるなら表示、無いなら存在しないと表示）
        for index, row in df.iterrows():
            slack_display(message,str(row[1]),str(row[5]),str(row[6]),str(row[3]),str(row[8]),str(row[4]),str(row[7]),str(row[0]),row[9])
    else:
        message.reply('登録されているお店がありません')
        

@listen_to(r'^店名\s(.*)$')
@respond_to(r'^店名\s(.*)$')
def display5(message,text):
    shop_name=text
    cur.execute("select * from food_gurume where shop_name glob '*{}*'".format(shop_name))
    df = pd.DataFrame(cur.fetchall())
    if df.shape[0]>=1: #0:縦の長さを指定 .shapeで大きさをとれる（もしdfにデータが１つ以上あるなら表示、無いなら存在しないと表示）
        for index, row in df.iterrows():
            slack_display(message,str(row[1]),str(row[5]),str(row[6]),str(row[3]),str(row[8]),str(row[4]),str(row[7]),str(row[0]),row[9])
    else:
        message.reply('登録されているお店がありません')

#価格で検索可能
@listen_to(r'^価格\s(.*)$')
@respond_to(r'^価格\s(.*)$')
def deisplay4(message,text):
    text=str(text)
    if text.isascii()and text.isdecimal():
        price=str(text)
        cur.execute("select * from food_gurume")
        df = pd.DataFrame(cur.fetchall())
        count=0
        for index, row in df.iterrows():
            if len(re.findall(r'\d+', row[3]))>0:
                int_price = re.findall(r'\d+', row[3])
                if int(int_price[0]) <= int(price):
                    count=count+1
                    slack_display(message,str(row[1]),str(row[5]),str(row[6]),str(row[3]),str(row[8]),str(row[4]),str(row[7]),str(row[0]),row[9])
        if count==0:
            message.reply('登録されてるお店がありません')
    else:
        message.reply('半角数字で正しく入力してください')


#APIの利用でお店のURLを取得
def hotpepperapi(shop_name,keyword,message):
    api_key=""
    #urllib.requestはURLへの接続、ファイルの読み込みを担当 urllib.parseはURLの解釈を担当
    api = "http://webservice.recruit.co.jp/hotpepper/gourmet/v1/?key={key}&name="+urllib.parse.quote_plus(shop_name,encoding='utf-8')\
        +"&keyword="+urllib.parse.quote_plus(keyword,encoding='utf-8')+"&range=5&order=4" #検索範囲3000ｍ、人気順に表示
    url=api.format(key=api_key)
    req = urllib.request.Request(url) #GETパラメータを追加したURLを生成 変数urlを処理しやすくするため、Requestオブジェクトに格納
    with urllib.request.urlopen(req) as response:
        xml_string = response.read()
    root = ET.fromstring(xml_string) 
    if int(root.find('{http://webservice.recruit.co.jp/HotPepper/}results_available').text)>=1:
        return root.find('{http://webservice.recruit.co.jp/HotPepper/}shop').find('{http://webservice.recruit.co.jp/HotPepper/}urls').find('{http://webservice.recruit.co.jp/HotPepper/}pc').text,\
               root.find('{http://webservice.recruit.co.jp/HotPepper/}shop').find('{http://webservice.recruit.co.jp/HotPepper/}genre').find('{http://webservice.recruit.co.jp/HotPepper/}name').text,\
               root.find('{http://webservice.recruit.co.jp/HotPepper/}shop').find('{http://webservice.recruit.co.jp/HotPepper/}name').text,\
               root.find('{http://webservice.recruit.co.jp/HotPepper/}shop').find('{http://webservice.recruit.co.jp/HotPepper/}photo').find('{http://webservice.recruit.co.jp/HotPepper/}pc').find('{http://webservice.recruit.co.jp/HotPepper/}l').text,\
               root.find('{http://webservice.recruit.co.jp/HotPepper/}shop').find('{http://webservice.recruit.co.jp/HotPepper/}access').text
    else:
        message.reply('HOTPEPPERに情報が存在しません。登録できません。')
        sys.exit()
        return "urlがみつかりません","ジャンルが見つかりません",shop_name,"なし","アクセスが見つかりません"
