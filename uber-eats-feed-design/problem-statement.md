Imagine we are building Uber Eats from scratch and we know we have a bunch of restaurants and eaters will provide their delivery location, and your job is to design a backend that will deliver a feed of restaurants that an eater can order food delivery from.
Functionally you have been Given a location, return a list of restaurants.
Think about solutioning these -
- Ranking of restaurants
- Scale of restaurants
- Delivery radius of a restaurant
- Rate of restaurants being added

You should focus on coming up with a basic end-to-end design first.

The subsequent portion will focus on scale issues, and other follow-up questions.

Scale: assume we have 10 million restaurants globally. Assume we support at least 10K views per second.
One question that might come up is on resolving restaurant state,
try to stray away from that and focus more on location search+ranking.
Focus on whether they can shard the dataset in a way that makes sense.
Sharding can happen along two ways (by location or restaurant ID).

Sharding Details:
Location: Used to find the list of restaurants.
Restaurant ID: Used to find restaurant details.
For v1 you can assume that restaurants are always open (don't worry about state).

Add the constraint that we sometimes have dynamic information that we need to filter the restaurants
from (restaurants taking a break from the platform, or we don't want certain restaurants to be ordered
from across the manhattan bridge for example). How would this is implemented?
Online filtering vs changing the search index.

Basic design starting with the API endpoints.
API endpoints should follow clear RESTful design principles with contracts defined b/w mobile and backend.
think through pagination properly.
What if a new restaurant is added right after their first search, how can we handle this?

create a design that accounts for a read-heavy workloads of the system.
I you want to suggest "Use elastic search", you should be able to explain how elastic search implements
this underneath the covers.

Challenges & Edge Cases:
Hotspots e.g. super dense areas like Manhattan.
Shard based on restaurant ID (mini K-d trees):
Shard the entire K-d tree across boxes (but each box only stores some set of restaurant id's).
You might have a fan-out problem depending on the number of boxes you shard the index over.

Geohashing:
The lookup key is just a grid id identifying an area and the value is all of the restaurants valid for this area.
The restaurants valid for a given geohash would be pre-computed offline or updated on writes.
Expect the candidate to be able to talk about how the geohash is populated.
If they select a geohash, talk about hyper-dense areas (Manhattan, India, etc) that a large amount of
restaurants per geohash.
Scaling storage.
Kd-trees:
log(n) lookup, dense areas are broken up by adding sub-trees.
Scaling challenge with this is if the K-d tree grows too big for one box, how do you shard the K-d tree?
What if a K-d tree spans multiple shards?
Shard based on branches and aggregate reads across shards.
Challenges & Edge Cases:
Hotspots e.g. super dense areas like Manhattan.
Shard based on restaurant ID (mini K-d trees):
Shard the entire K-d tree across boxes (but each box only stores some set of restaurant id's).
You might have a fan-out problem depending on the number of boxes you shard the index over.

Anything outside of these two approaches usually come with a significant increase in
complexity, how the underlying system is
rebuilt in the event of failure.