# Conference Central
Conference Central is a cloud-based API server built on Google Cloud Platform. 
This project is part of [Udacity’s Full Stack Web Developer Nanodegree](https://www.udacity.com/course/nd004).

The API supports the following functionality:

- User authentication 
- Create, read, update conferences and sessions
- Supports multi-inequality queries for Conferences and Sessions
- Register/unregister for conferences
- Add/remove sessions to user's wish list
- Task Queues and Cron Jobs such as:
    - Email confirmation upon conference creation
    - Update conference announcements in Memcache. (updates every hour)
    - Update most recent featured speaker in Memcache. (checked after session creation)  

You can checkout the website demo [here][9]. Currently, the demo does not support all functionality. 
To access all functionality you must use [API Explorer][8]

## NDB Entities (Models)
- Profile:
    - is an "ancestor" of Conference, for the conference creator
    - "has" Conferences, when registering to a conference
    - "has" Sessions, when adding session to user's wish list
- Conference:
    - is a sibling of Profile
    - is an "ancestor" of sessions
- Session:
    - is a sibling of Conference
    - contains a Speaker (structured property)
- Speaker:
    - is a structured property. 

Sessions can have speakers that are not registered users. For this reason, `Speaker` was chosen to be a structured property. Structured properties are defined using the same syntax as model classes but they are not full-fledged entities.

Conference was chosen to be an ancestor of Session so we can use the conference key to obtain all sessions registered in the conference.
If we implemented a "has a" relationship, we would first have to query the conference to obtain the session keys, then make an additional query to retrieve the sessions.

Note:
- Any properties that represented a date, YYY-MM-DD, or a time, HH:MM, were updated to to use DateProperty and TimeProperty.



## Task 3: The Query Problem

Let’s say that you don't like workshops and you don't like sessions after 7 pm. 
How would you handle a query for all non-workshop sessions before 7 pm?
- `Session.query(Session.typeOfSession != 'workshop', Session.startTime < '19:00')`

What is the problem for implementing this query?
- NDB Datastore API doesn't support using inequalities for multiple properties.

What ways to solve it did you think of?
- One way to solve this problem is to let datastore handle the first inequality and any additional inequalities should be implemented in python.

The test case `testTask3QueryProblem` found in [test/test_conference.py](test/test_conference.py), solves this problem in a testing environment.

## Additional Queries

`removeSessionFromWishlist()` - Removes the given session from user's wish list.

`querySessions()` - Given a `SessionQueryForms`, returns a set of filtered sessions.

The following filters are supported:

 - NAME
 - DURATION
 - TYPE_OF_SESSION
 - DATE
 - START_TIME
 - SPEAKER

Both `querySessions` and `queryConferences` have been redone to support multiple inequality filters.


## Products
- [App Engine][1]

## Language
- [Python][2]

## APIs
- [Google Cloud Endpoints][3]
- [NDB Datastore API][10]
- [Memcache API][11]
- [Mail API][12]

## How to Run Tests
1. In [test/runner.py](test/runner.py), locate the comment `UPDATE PATHS` and update the current paths to include the App Engine libraries and yaml (included in the App Engine SDK). If you are using a Mac and used Google App Engine SDK installer, you will most likely not have to change anything :)
    - If you are still having trouble with this step, please checkout this [guide][7]
2. To run all tests, open the terminal in your projects root directory then run: `python test/runner.py`


## How to Run on Local Server
1. Update the value of `application` in `app.yaml` to the app ID you
   have registered in the App Engine admin console and would like to use to host
   your instance of this sample.
1. Update the values at the top of `settings.py` to
   reflect the respective client IDs you have registered in the
   [Developer Console][4].
1. Update the value of CLIENT_ID in `static/js/app.js` to the Web client ID
1. (Optional) Mark the configuration files as unchanged as follows:
   `$ git update-index --assume-unchanged app.yaml settings.py static/js/app.js`
1. Run the app with the devserver using `dev_appserver.py DIR`, and ensure it's running by visiting your local server's address (by default [localhost:8080][5].)
1. (Optional) Generate your client library(ies) with [the endpoints tool][6].
1. Deploy your application.


[1]: https://developers.google.com/appengine
[2]: http://python.org
[3]: https://developers.google.com/appengine/docs/python/endpoints/
[4]: https://console.developers.google.com/
[5]: https://localhost:8080/
[6]: https://developers.google.com/appengine/docs/python/endpoints/endpoints_tool
[7]: https://cloud.google.com/appengine/docs/python/tools/localunittesting?hl=en#Python_Writing_Datastore_and_memcache_tests
[8]: https://apis-explorer.appspot.com/apis-explorer/?base=https://compact-arc-103415.appspot.com/_ah/api#p/conference/v1/
[9]: https://compact-arc-103415.appspot.com/#/
[10]: https://cloud.google.com/appengine/docs/python/ndb/
[11]: https://cloud.google.com/appengine/docs/python/memcache/
[12]: https://cloud.google.com/appengine/docs/python/mail/
