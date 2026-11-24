---
status: accepted
---

# 0001. PacePro splits come from our own algorithm, tuned black-box

garminconnect has no call to create a PacePro plan. Garmin Connect's website computes each
split's target pace in the browser and posts the finished splits, so creating a plan means
computing the splits ourselves. We write our own pacing algorithm and tune it only against
Garmin's output for known inputs. Nobody working on it reads Garmin's web code, because
copying or porting that code would publish Garmin's copyrighted code in this public repo.
Plans are written through the same private endpoint the website uses (#133, #141).

Revisit when garminconnect adds a public call to create PacePro plans.
