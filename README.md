# Karmabot for Slack

This is an implementation of Karma in Python that should be fairly robust to handle a largerish deployment.

## Features

* Karma rate-limiting:  Only 60 Karma operations per hour from any user
* Separation of thing/user/group/channel Karma
* Top and Bottom list for all, things, users, channels
* Karma expiration
* General Karma statistics
* Badges


## What is Karma?

Karma is a quazi-reputation system.  You may have used it in other Chat systems.  Simply put, you can add a `++` or `--` to the end of subject to add or remove karma.
Anyone (except bots) can give Karma.  Karma isn't a perfect system — it can be gamed, but it can be a fun way to show your gratitude when someone helps you out.

## What are badges?

Badges are bit of an experiment right now.  When a user's karma is shown (either from normal karma operations or a show command) any badges they have will be displayed with the karma score.  Badges can only be created by the Slack admins, and only badge owners can give them to a user.  A user may choose to remove any of their own badges, too.

The idea is badges should be special, unique, and convey some meaning. For now, the intent is to have badges be limited to groups of 20 or less people, and have any one person have no more than 5 badges (ideally between 0 and 2 badges). No limits are enforced (yet) as this is an experiment. If you have an idea for how badges could be useful, please let us know!

## Architecture

This implementation uses Flask and MongoDB.


The Flask web service listens for the events from Slack and executes them in a separate thread using `flask-executor`. MongoDB is used to store the Karma operations.

### MongoDB

Karma operations are stored as documents in the collection named after the Workspace ID (aka `team_id`).  The documents look like:

```
{
    "_id" : ObjectId("5a9c5da940ea97000f9cf8dc"),
    "expires" : ISODate("2018-06-02T20:57:13.280Z"),
    "date" : ISODate("2018-03-04T20:57:13.280Z"),
    "subject" : "foo",
    "type" : "thing",
    "gifter" : "U12345678,
    "quantity" : 1
}
```

For the `type`, it can be one of `thing`, `user`, `channel`, or `group`. Users, Channels, and Groups should be stored by their ID, not the display name, to support name changes without loosing Karma.

The MongoDB service should be set up initially with indexes to improve performance, and expire old Karma.

```
db.WKSPCID.createIndex( { "expires": 1 }, { expireAfterSeconds: 0 } )
```

## Setup

* Set up MongoDB somewhere, should be persistent if you don't want to loose your Karma
* Set up a Metrics service, something that accepts InfluxDB line protocol over a TCP port.  See the `docker-compose.yml` for an example of a Telegraph instance that does this. 
* Create the app entry in `api.slack.com/apps`.
  * Create `/karma` command pointed to the proper HTTP endpoint for commands
    * Make sure to select "Escape channels, users, and links"
  * Create `/badge` command pointed to the proper HTTP endpoint for commands
    * Make sure to select "Escape channels, users, and links"
* Start the Karmabot instance somewhere.  Its designed to be a Docker service, and configuration is handled via environment variables. 
* Update the app entry in `api.slack.com/apps`:
 * Create event subscriptions and point at the proper HTTP endpoint for events. Subscribe to Bot Events:
     * `app_mention`
     * `message.channels`
     * `message.groups`
  * Set OAuth permissions to include:
    * `bot`
    * `commands`
    * `channels:write`
    * `chat:write:bot`
    * `im:write`
    * `usergroups:read`
* Invite the Karma bot into channels you wish to track Karma

### Environment Variables

As mentioned, configuration is handled via environment variables.  Here is the list of things you can configure:
 * `VERIFICATION_TOKEN` The verification from your Slack App config. There is no default, you must set this.
 * `MONGODB` The MongoDB URI (including username and password if applicable).  Defaults to `mongodb://localhost:27017`
 * `SLACK_EVENTS_ENDPOINT` The base URI to accept Slack events on.  Defaults to `/slack_events`
 * `KARMA_RATE_LIMIT` Number of Karma operations per hour a user can do.  Defaults to `60`
 * `KARMA_TTL` How quickly Karma expires, in days.  Defaults to `90`
 * `KARMA_COLOR` The highlight color to use when Karmabot posts messages. Defaults to `#af8b2d`
 * `FAKE_SLACK` Only used for testing.  When set to `True` it will not actually connect to Slack, and instead mocks out the Slack services.

Since the app may be installed to multiple workspaces, there are two ways to handle the OAuth and Bot access tokens, using Hashicorp Vault or environment variables.

Using Vault requires more infrastructure, but allows for dynamically adding workspaces without needing to restart services.  Using environment variables is simpler, but requires restarting the service when adding new workspaces.


To use environment variables, leave `USE_VAULT` unset, or set it to `False`. Then store the tokens like this:

 * `ACCESS_{workspace_id}` The OAuth Access Token for workspace `{workspace_id}`
 * `BOT_{workspace_id}` The Bot Access Token for workspace `{workspace_id}`
 

To use Vault, set

 * `USE_VAULT` to `True` . Defaults to False.
 * `VAULT_URI` to the Vault URI to connect to.  Defaults to None.
 * `VAULT_TOKEN` to the Vault authentication token. Defaults to None.
 * `VAULT_BASE` to the location in Vault where tokens can be found.  Defaults to `secrets`

Store the tokens in the `VALUT_BASE` location with the name `access_{workspace_id}.txt` where `{workspace}` is the workspace ID (case sensitive), using the kv1 method.  For example:

```
vault write secret/secrets/access_T1234.txt value=xoxa-1234-5678
vault write secret/secrets/bot_T1234.txt value=xoxb-1234-5678
```  

## How to contribute

This is intended to be a community driven project. Feel free to submit a PR if you think you can improve it, or just open an issue if you have an idea but can't implement it.

We won't take every feature request, but if its a good idea, we will take it in.


## Contributors

* Jay Kline (@slushpupie)
* Jordan Sussman (@JordanSussman)
* Jim Male (@JMaleTarget)
* Emmanuel Meinen (@meinenec)
* James Bell (@lemoney)
* Thiti Vutisalchavakul (@vutisat)
