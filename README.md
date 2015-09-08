# Conference Central
Conference Central is a cloud-based API server built on Google Cloud Platform.

The API supports the following functionalities:
- User authentication
- Create, read, update conferences and sessions
- Register/unregister for conferences
- Add/remove sessions to user's wish list
- Supports multi inequality queries for Conferences and Sessions

## Products
- [App Engine][1]

## Language
- [Python][2]

## APIs
- [Google Cloud Endpoints][3]

## How To Run Tests
1. In file `test/runner.py`, locate the comment `UPDATE PATHS` and update the current paths to include the App Engine libraries and yaml (included in the App Engine SDK). If you are using a Mac and used Google App Engine SDK installer, you will most likely not have to change anything :)
2. To run all tests, open the terminal in your projects root directory and run `python test/runner.py`
For those having trouble with step one, please checkout this [guide][7]

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
