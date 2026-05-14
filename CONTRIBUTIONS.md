# Who Did What

A quick note on contributions for FieldCore.

Up front: the GitHub history is not a great representation of who did what on this project. A huge amount of the work was hardware, wiring, and integration between the different parts of the system, none of which really shows up in commits. A good chunk of the early work also happened before we had GitHub set up at all. You'll also notice that Alex has a lot of commits — that was intentional. He and Turner did most of their work pair programming on Alex's machine, with the actual Raspberry Pi plugged in, so almost everything they wrote together landed under his account. The breakdown below is what actually happened.

## Software

**Brody Nelson** got the project off the ground. He set up the API contract and the database, built the initial backend, and kept things moving in the early stretch when nothing existed yet.

**Turner Van Duser** owned the application layer. He drove the product decisions on the web app — what the dashboard should look like, how it should behave, and what the user experience should be.

**Alex Wexler** focused on the Raspberry Pi software and parts of the UI. For the last month or so, he and Turner pair programmed on one machine, which is why a lot of the later commits show up under one account.

**Dominic Rios** owned the Arduino. He wrote the firmware, handled the sensor code, and made sure the Arduino side integrated cleanly with the rest of the stack.

## Hardware

**Ian Cooper**, **Carson Agee**, and **Nate Spencer** ran the physical side of the project, and that was a real job, not a side task. FieldCore has to live outdoors, so the enclosures had to actually keep water out and hold the sensors in the right places after getting planted in dirt.

They designed and built both the Pi base station enclosure and the Arduino field node enclosures from scratch, including all the wiring and assembly. By the time the software team picked up a node, it was ready to run. When something broke in the field, they handled the hardware side on the spot.
