# Privacy Policy — whoop-mcp

_Last updated: 29 July 2026_

## Overview

`whoop-mcp` is a personal, single-user integration that connects the author's own
WHOOP account to a locally running MCP (Model Context Protocol) server. It is not
a commercial product, is not offered to third parties, and has no user accounts.

## Who operates this application

This application is operated privately by an individual for personal use only.
Contact: d.lentz@me.com

## What data is accessed

With the WHOOP member's explicit OAuth consent, the application may read:

- Recovery data (recovery score, heart rate variability, resting heart rate, SpO2, skin temperature)
- Sleep data (duration, sleep stages, performance, consistency, efficiency, respiratory rate)
- Cycle data (day strain, calories, average and maximum heart rate)
- Workout data (sport, strain, heart rate zones, distance, elevation)
- Body measurements (height, weight, maximum heart rate)
- Basic profile data (name, email)

## How data is used

Data is used exclusively to display the member's own health and fitness metrics
within the member's own local tooling. It is not analysed for any commercial
purpose, not aggregated with other people's data, and not used to train models.

## Where data is stored

All data is stored locally on the operator's own computer, in a local database
file. OAuth tokens are stored in the operating system's secure credential store
(macOS Keychain).

No data is transmitted to any server operated by the author, to any cloud
service, or to any analytics or advertising provider. There is no backend.

## Data sharing

No data is sold, rented, shared, or otherwise disclosed to any third party.

## Data retention and deletion

Locally stored data is retained until the operator deletes it. Deleting the local
database file and revoking the application's access in the WHOOP account settings
removes all stored data and terminates all access.

## Revoking access

Access can be revoked at any time from within the WHOOP app or via the WHOOP API
endpoint `DELETE /v2/user/access`. Revocation takes effect immediately.

## Security

Access and refresh tokens are held in the macOS Keychain rather than in plain
text. All communication with the WHOOP API uses HTTPS.

## Changes to this policy

Any changes will be published in this file in the public repository at
https://github.com/d00ennis/whoop-mcp

## Contact

Questions regarding this policy: d.lentz@me.com
