from flask import Flask, render_template, request
import datetime

import pandas as pd
import json
import matplotlib
matplotlib.use('Agg')
 
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns 

from sqlalchemy import create_engine
import io
import MySQLdb as mdb

import re
from geojson import Point, Feature, FeatureCollection





app = Flask(__name__, static_folder='static')

@app.route('/introduction')
def introduction():
    return render_template('introduction.html')

@app.route('/Advisory_service_search')
def Advisory_service_search():
    return render_template('Advisory_service_search.html')


@app.route('/Advisory_service_result', methods = ['POST', 'GET'])
def Advisory_service_result():
    infos=[]
    #get information from the html form
    if request.method == 'POST':
        result = request.form
        style_name = result["Style"]
        start_date = datetime.datetime.strptime((result["Start_date"]), '%Y-%m-%d')
        end_date = datetime.datetime.strptime((result["End_date"]), '%Y-%m-%d')
        state_name = result["Location"]
        
        #connect to database
        con = 'mysql://{user}:{password}@{host}:{port}/{db}'.format(
                      user = 'root',                                                                     
                      password = '<password>',
                      host = '52.5.6.75',
                      port=3306,                                              
                      db = 'Project'                                            
                      );
        engine_db = create_engine(con)        
        
        #Plot according to time
        query_template_date = '''SELECT concert_date, avg(average_price) AS price 
                                 FROM Project.seatgeek_concerts 
                                 WHERE concert_date > %(start_date)s
                                 AND concert_date < %(end_date)s
                                 GROUP BY concert_date;
                              '''
        parameters={"start_date": start_date, "end_date": end_date}
        df_date = pd.read_sql(query_template_date,con=engine_db,params = parameters,)
        df_date['concert_date']=pd.to_datetime(df_date['concert_date'], format='%Y-%m-%d')
        df_date = df_date.dropna()
        
        price_date=df_date['price'].mean()
        
        df_date2 = df_date.set_index('concert_date')
        plot_date = df_date2.plot()
        fig = plot_date.get_figure()
        
        now=datetime.datetime.now()
        now_=str(now)[:10]+str(now)[12:]
        filename_time= "static/"+str(start_date)[:10]+"-"+str(end_date)[:10]+now_+'.png'
        fig.savefig(filename_time)
        plt.close(fig)
        
        url_time="http://ec2-52-203-169-211.compute-1.amazonaws.com:5000/" + filename_time
        info_time={"price":price_date, "url":url_time}
        infos.append(info_time)
        
        #Define data-cleaning functions
        def belowIQR(dataframe, columnname):
            Q3 = float(np.percentile(dataframe[columnname], 75))
            Q1 = float(np.percentile(dataframe[columnname], 25))
            IQR = Q3 - Q1
            belowIQR = Q1 - 1.5*IQR
            return belowIQR

        def aboveIQR(dataframe, columnname):
            Q3 = float(np.percentile(dataframe[columnname], 75))
            Q1 = float(np.percentile(dataframe[columnname], 25))
            IQR = Q3 - Q1
            aboveIQR = Q3 + 1.5*IQR
            return aboveIQR

        def price_clean(dataframe, columnname):
            dataframe = dataframe[dataframe[columnname] >= 0]
            dataframe = dataframe.loc[(dataframe[columnname] < aboveIQR(dataframe, columnname)) 
                        & (dataframe[columnname] > belowIQR(dataframe, columnname))]
            return dataframe
    
        def state_symbol(address):
            regex = re.compile('[A-Z][A-Z]')
            matches = regex.finditer(str(address))
            for match in matches:
                return match.group(0)
        
        #Plot according to location
        #Seatgeek artists + genre 
        query_template_location = '''select *
                    from Project.seatgeek_artists a
                    join Project.seatgeek_concerts c on a.artist = c.artist
                    WHERE c.concert_date > %(start_date)s
                    AND c.concert_date < %(end_date)s                  
                    '''
        parameters={"start_date": start_date, "end_date": end_date, }
        seatgeek_joined = pd.read_sql(query_template_location,con=engine_db,params = parameters,)
       #Creating dataframe for Seatgeek(State) Price Analysis
        seatgeek_cleaned = seatgeek_joined
        seatgeek_cleaned = seatgeek_cleaned.dropna()
        seatgeek_cleaned['state'] = seatgeek_cleaned['address'].apply(lambda x: state_symbol(x))
        seatgeek_cleaned['popularity'] = seatgeek_cleaned.popularity.astype(float) #Change popularity to float
        seatgeek_cleaned = price_clean(seatgeek_cleaned, 'average_price')
        #get price
        price_location=seatgeek_cleaned['average_price'].mean()
        
       # Create the data
        rs = np.random.RandomState(1979)
        x = rs.randn(500)
        g = np.tile(list("ABCDEFGHIJ"), 50)
        df = pd.DataFrame(dict(x=x, g=g))
        m = df.g.map(ord)
        df["x"] += m
        
        state = seatgeek_cleaned[seatgeek_cleaned['state'] == state_name]
        state_avg = state['average_price']
        total_avg = seatgeek_cleaned['average_price']
        
        #Plotting
        sns.set(style="white", rc={"axes.facecolor": (0, 0, 0, 0)})
        fig, ax = plt.subplots(figsize=(12, 8))
        totaldist = sns.kdeplot(total_avg, shade=True, color="#8c8ba0", linewidth = 1.5, linestyle = "--", label = "United States")
        totalline = plt.axvline(total_avg.mean(), color='#8c8ba0', linestyle= "-", linewidth=2) #BLUE
        statedist = sns.kdeplot(state_avg, shade=False, color="#9c00b7", alpha = 0.5, linewidth = 3, label = "{}".format(state_name))
        stateline = plt.axvline(state_avg.mean(), color='#9c00b7', linestyle= "-", linewidth=2)
        ax.set_title('Distribution of Average Prices in {} against US'.format(state_name), size = 18, x = 0.4, y = 1.05)
        ax.set_xlabel('Price')
        plt.legend(loc='center right')
        #ax.text(200, 0.010,'US Mean Line',fontsize=10, color = 'black')
        sns.despine(left=True, bottom=True, right=True)
        filename_location= "static/"+ state_name +"_output.png"
        fig.savefig(filename_location,dpi=300)
        url_location="http://ec2-52-203-169-211.compute-1.amazonaws.com:5000/" + filename_location
        
        info_location={"price":price_location, "url":url_location}
        infos.append(info_location)
        
    
        
        #Heatmap concert count for last five years
        #Songkick dates
        query_template_songkick_date = '''select artist, concert_date, city
                            from Project.songkick
                            where concert_date > '2012-00-00'
                         '''
        songkick_date = pd.read_sql(query_template_songkick_date,con=engine_db,)
        
        songkick_date2 = songkick_date
        songkick_date2['state'] = songkick_date2['city'].apply(lambda x: state_symbol(x))
        
        state = songkick_date2[songkick_date2['state'] == state_name]
        state['year'] = state['concert_date'].apply(lambda x: x.year)
        state['month'] = state['concert_date'].apply(lambda x: x.strftime("%b"))
        
        pivot_dates = pd.pivot_table(state, 
                       values='artist', 
                       index=['month'], # rows
                       columns=['year'], # columns
                       aggfunc='count') 

        pivot_dates = pivot_dates.fillna(0)
        
        #sns.set()
        #Draw a heatmap with the numeric values in each cell
        fig, ax = plt.subplots(figsize=(9, 9))
        heatmapplot = sns.heatmap(pivot_dates, annot=True, fmt="d", linewidths=.5, ax=ax, cmap="BuPu")
        plt.yticks(rotation=0)

        ax.set_title('Heatmap: 5 Years of Concerts in {}'.format(state_name), size = 18, color = 'black', x = 0.50, y = 1.03)

        fig = heatmapplot.get_figure()
        now=datetime.datetime.now()
        now_=str(now)[:10]+str(now)[12:]
        filename_heatmap = "static/heatmap-"+now_+".png"
        fig.savefig(filename_heatmap,dpi=300)
        url_heatmap="http://ec2-52-203-169-211.compute-1.amazonaws.com:5000/" + filename_heatmap
        
        info_heatmap={"price":0, "url":url_heatmap}
        infos.append(info_heatmap)
        
        #Top Artists in Location
        #Songkick dates
        query_template_songkick_popular = '''select a.artist, a.popularity, s.concert_date, s.city, s.role
                            from Project.seatgeek_artists a
                            join Project.songkick s on a.artist = s.artist
                            where s.city like %(state)s and concert_date > '2012-00-00'
                            order by popularity desc
                         '''
        parameters={"state":"%"+state_name+"%",}
        songkick_popular = pd.read_sql(query_template_songkick_popular,con=engine_db,params = parameters,)

        songkick_popular['popularity'] = songkick_popular.popularity.astype(float)
        songkick_popular['artist'] = songkick_popular['artist'].apply(lambda x: str(x))
        
        #Popularity
        popularity = songkick_popular[['artist','popularity']]
        popularity = popularity.groupby('artist').mean()

        #Number of concerts
        num_concerts = songkick_popular[['artist', 'city']]
        num_concerts = num_concerts.groupby('artist').count()

        #Number of headlines
        headlines = songkick_popular[['artist', 'role']]
        headlines = headlines.groupby('artist')['role'].apply(lambda x: x[x.str.contains('headline')].count())
        
        #Combine together
        merged = pd.merge(num_concerts, popularity, left_index=True, right_index=True)
        merged['headline'] = headlines
        merged = merged.rename(columns={'city': 'concerts'})
        merged = merged.reset_index()
        merged = merged.sort_values(by='concerts', ascending=False)
        merged = merged.head(50)
        
        # Load the dataset
        #crashes = sns.load_dataset("car_crashes")

        # Make the PairGrid
        g = sns.PairGrid(merged.sort_values("concerts", ascending=False), x_vars=merged.columns[1:4], y_vars= ["artist"], size=12, aspect=.25)

        # Draw a dot plot using the stripplot function
        g.map(sns.stripplot, size=12, orient="h", palette="BuPu_r", edgecolor="gray") 
        #_r to reverse palette

        # Use semantically meaningful titles for the columns
        titles = ["Number of Concerts", "Overall Popularity", "Shows Headlined"]


        for ax, title in zip(g.axes.flat, titles):
            # Set a different title for each axes
            ax.set(title=title)

            # Make the grid horizontal instead of vertical
            ax.xaxis.grid(False)
            ax.yaxis.grid(True)

        g.fig.subplots_adjust(hspace=0, wspace=2.0) #edit wspace to shorten gap between subplots
        sns.despine(left=True, bottom=True)

        fig = g.fig
        now=datetime.datetime.now()
        now_=str(now)[:10]+str(now)[12:]
        filename_pairplot="static/pairplot"+now_+".png"
        fig.savefig(filename_pairplot, dpi=300, bbox_inches="tight")
        url_pairplot="http://ec2-52-203-169-211.compute-1.amazonaws.com:5000/" + filename_pairplot
        
        info_pairplot={"price":0, "url":url_pairplot}
        infos.append(info_pairplot)
        
        #Price vs streamcount
        #Seatgeek artists + genre 
        query_template_last_fm = '''select c.artist, c.average_price, l.playcount, a.genres 
                    from Project.seatgeek_concerts c
                    join Project.lastfm_cleaned l on c.artist = l.artist_name 
                    join Project.seatgeek_artists a on a.artist = l.artist_name
                    '''
        last_fm = pd.read_sql(query_template_last_fm,con=engine_db,)
        
        #Creating dataframe for Seatgeek(State) Price Analysis
        lastfm_cleaned = last_fm #remove NaNs
        lastfm_cleaned = lastfm_cleaned.dropna()
        lastfm_cleaned = price_clean(lastfm_cleaned, 'average_price')
        lastfm_cleaned = price_clean(lastfm_cleaned, 'playcount')
        lastfm_cleaned2 = lastfm_cleaned[lastfm_cleaned['genres'].str.contains(style_name)]
        streaming = lastfm_cleaned2[['average_price', 'playcount']]
        #get price
        price_stream = streaming.average_price.mean()
        #Plotting
        sns.set(style= "darkgrid", color_codes=True)
        g = sns.jointplot("playcount", "average_price", data=streaming, kind="reg",color="#4682B4", size=7)
        fig = g.fig
        now=datetime.datetime.now()
        now_=str(now)[:10]+str(now)[12:]
        filename_stream="static/stream"+now_+".png"
        fig.savefig(filename_stream, dpi=300, bbox_inches="tight")
        url_stream="http://ec2-52-203-169-211.compute-1.amazonaws.com:5000/" + filename_stream
        
        info_stream={"price":price_stream, "url":url_stream}
        infos.append(info_stream)
        
        #Price and Popularity
        #Seatgeek artists + genre 
        query_template_seatgeek_joined = '''select * from Project.seatgeek_artists a
                           join Project.seatgeek_concerts c on a.artist = c.artist
                        '''
        seatgeek_joined = pd.read_sql(query_template_seatgeek_joined,con=engine_db,)
        
        
        #Creating dataframe for Seatgeek(State) Price Analysis
        seatgeek_cleaned = seatgeek_joined #remove NaNs
        seatgeek_cleaned = seatgeek_cleaned.dropna()
        seatgeek_cleaned['state'] = seatgeek_cleaned['address'].apply(lambda x: state_symbol(x))
        seatgeek_cleaned['popularity'] = seatgeek_cleaned.popularity.astype(float) #Change popularity to float
        seatgeek_cleaned = price_clean(seatgeek_cleaned, 'average_price')
        seatgeek_cleaned = price_clean(seatgeek_cleaned, 'popularity')
        
        rap = seatgeek_cleaned[seatgeek_cleaned['genres'].str.contains(style_name)]
        rap = rap[['average_price', 'popularity']]
        
        sns.set(style="darkgrid", color_codes=True)
        g = sns.jointplot("popularity", "average_price", data=rap, kind="reg",color="#9370DB", size=7)
        fig = g.fig
        now=datetime.datetime.now()
        now_=str(now)[:10]+str(now)[12:]
        filename_popularity="static/popularity"+now_+".png"
        fig.savefig(filename_popularity, dpi=300, bbox_inches="tight")
        url_popularity="http://ec2-52-203-169-211.compute-1.amazonaws.com:5000/" + filename_popularity
        
        info_popularity={"price":0, "url":url_popularity}
        infos.append(info_popularity)
        
    return render_template('Advisory_service_result.html', infos=infos)



@app.route('/Industry_overview_choose')
def Industry_overview_choose():
    return render_template('Industry_overview_choose.html')


#display concert info for top 50 artists according to lastfm. Some artists don't have upcoming concerts
@app.route('/Industry_overview_result_artist')
def Industry_overview_result_artist():
    #connect to database
    con = mdb.connect(host = '52.5.6.75', 
                  user = 'root',
                  database = 'Project',
                  passwd = '<password>', 
                  charset='utf8', use_unicode=True);
    cur = con.cursor(mdb.cursors.DictCursor)
    #Find top 50 artists who played most frequently in last 5 years
    cur.execute('''SELECT artist, COUNT(artist) AS counts 
               FROM Project.songkick
               WHERE concert_date > '2012-00-00'
               GROUP BY artist
               ORDER BY counts DESC
               LIMIT 50''')
    artists = cur.fetchall()
    cur.close()

    artists_info=[]
    for artist in artists:
        artist_name = artist["artist"]
        total_concerts = artist["counts"]
        
        #Find their photos
        cur = con.cursor(mdb.cursors.DictCursor)
        query_template_img= ('''SELECT img_url 
                  FROM Project.lastfm_cleaned 
                  WHERE artist_name = %s
                ''')
        cur.execute(query_template_img,(artist_name,))
        img_url = cur.fetchone()
        artist_img_url = img_url["img_url"]
        
        #Find their real name to replace their id we created
        query_template_name= ('''SELECT artist, image_url 
                                  FROM Project.lastfm
                                  WHERE image_url = %s ''')
        cur.execute(query_template_name,(artist_img_url,))
        name = cur.fetchone()["artist"]
     
        #Get information about their upcoming concerts 
        query_template_price= ('''SELECT artist, AVG(average_price) AS avg_price, address 
                              FROM Project.seatgeek_concerts 
                              WHERE artist= %s
                              GROUP BY address ''')
        cur.execute(query_template_price,(artist_name,))
        artist_concerts = cur.fetchall()
        cur.close()
    
        concerts_info=""
        for concert in artist_concerts:
            if concert["artist"] == artist["artist"]:
                if concert["avg_price"] != None:
                    location=concert["address"]
                    price=int(concert["avg_price"])
                
            
                    concert_info="Address: "+ location + "; "+"Average Ticket Price: "+ str(price) + ". "
                    concerts_info+= concert_info
        if concerts_info !="":  
            artist_info={
                 "artist_name": name,
                 "total_concerts": total_concerts,
                 "artist_img_url": artist_img_url,
                 "concerts_info": concerts_info
                }
            artists_info.append(artist_info)
   
    return render_template('Industry_overview_result_artist.html', artists_info = artists_info )




@app.route('/Industry_overview_result_location')
def Industry_overview_result_location():
    #connect to database
    con = mdb.connect(host = '52.5.6.75', 
                  user = 'root',
                  database = 'Project',
                  passwd = '<password>', 
                  charset='utf8', use_unicode=True);
    cur = con.cursor(mdb.cursors.DictCursor)
    
    #Find top 100 cities in US where most concerts took place in last five years
    cur.execute('''SELECT city, avg(latitude) as latitude, avg(longitude) as longitude, count(city) as count_city 
               FROM Project.songkick
               WHERE city LIKE '% US%'
               AND concert_date > '2012-00-00'
               GROUP BY city
               ORDER BY count_city desc
               LIMIT 100;''')
    locations_info = cur.fetchall()
    cur.close()
    
    concerts_geojson=[]
    
    #Get infomation about city name, latitude, longitude and concert count
    for location_info in locations_info:
        count =  location_info["count_city"]
        lat = round(location_info["latitude"],2)
        lon = round(location_info["longitude"],2) 
    
        regex_state = re.compile(r'\, (\w+)\,')
        text_state = location_info["city"]
        matches_state = regex_state.finditer(text_state)
    
        for match_state in matches_state:
            state = match_state.group(1)
            
            regex_city = re.compile(r'^((\w|\ )+)\,')
            text_city = location_info["city"]
            matches_city = regex_city.finditer(text_city)
            for match_city in matches_city:
                city_raw = match_city.group(1)
            
                regex = re.compile(r'(\w+)(( )(\w+))?')
                text = city_raw
                matches = regex.finditer(text)
                for match in matches:
                    if match.group(3)!= None:
                        city = match.group(1)+match.group(4)
                    else:
                        city = match.group(1)
                    concert_geojson={"city": city, 
                                     "total_concerts": count,
                                     "lat": lat,
                                     "lon": lon}
                    concerts_geojson.append(concert_geojson)
         
   
    my_feature_list=[]
    for concert_geojson in concerts_geojson:
        lon = float(concert_geojson["lon"])
        lat = float(concert_geojson["lat"])
        my_point = Point((lon, lat))
        my_feature = Feature(geometry=my_point, properties={"city": concert_geojson["city"], 
                                           "total_concerts": concert_geojson["total_concerts"]})
        my_feature_list.append(my_feature)
    geodatasets = FeatureCollection(my_feature_list)
    

    return render_template('Industry_overview_result_location.html', geodatasets = geodatasets)




@app.route('/static/<path:path>')
def static_proxy(path):
    return app.send_static_file(path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug= True)




