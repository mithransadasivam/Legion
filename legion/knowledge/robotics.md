## Convex model-predictive control let a quadruped run and jump in real time
Source: Di Carlo, Wensing, Katz, Bledt, Kim et al., 2018 -- MIT Cheetah 3, IEEE/RSJ IROS (related arXiv:1909.06586 covers the MIT Cheetah 3 / Mini Cheetah control stack)
Keywords: legged locomotion, quadruped, model predictive control, MPC, MIT Cheetah, dynamic running, jumping, whole-body control

MIT's Cheetah 3 team showed that a simplified rigid-body dynamics model, solved as a convex optimization problem at each control cycle, is fast enough to plan ground reaction forces for a running and jumping quadruped in real time. This let the robot handle bounding gaits, blind stair climbing, and recovery from pushes without pre-planned footstep trajectories. The approach is well established in industry and academia as a strong non-learned baseline, though it depends on a reasonably accurate model of the robot's mass and inertia and can struggle on terrain with unpredictable, discontinuous contact like loose gravel.

## A single neural adaptation module lets legged robots handle terrain never seen in training
Source: Kumar, Fu, Pathak, Malik, 2021 -- "RMA: Rapid Motor Adaptation for Legged Robots," arXiv:2107.04034
Keywords: sim-to-real, reinforcement learning, quadruped, legged locomotion, domain adaptation, proprioception, A1 robot

RMA trains a base walking policy in simulation alongside a small "adaptation module" that infers hidden environment properties (friction, payload, terrain softness) purely from the robot's own joint sensors, with no vision. Deployed zero-shot on a Unitree A1 quadruped, it adapted within fractions of a second to sand, mud, slopes, and a 12 kg payload without any real-world fine-tuning. It's a widely cited proof that proprioception alone can carry a lot of terrain generalization; the main limitation is that it still struggles with terrain that requires foresight, like gaps or stairs it cannot feel until a leg is already on them.

## A blind bipedal robot learned to climb real stairs using only body-sensing
Source: Siekmann, Godse, Fern, Hurst, 2021 -- "Blind Bipedal Stair Traversal via Sim-to-Real Reinforcement Learning," arXiv:2105.08328
Keywords: bipedal locomotion, humanoid, Cassie, stairs, sim-to-real, reinforcement learning, proprioception

Oregon State and Agility Robotics researchers trained a policy entirely in simulation, using domain randomization over stair heights and slopes, and deployed it on the human-scale Cassie biped with its cameras covered. The robot reliably went up and down stairs, curbs, and irregular steps it had never been shown, relying only on joint encoders and an IMU. It was one of the first demonstrations of blind stair traversal on a full-scale bipedal robot; it does not generalize to obstacles requiring path choice, since the robot has no idea what's ahead until it steps on it.

## A quadruped taught itself agile parkour skills through curriculum reinforcement learning
Source: Hoeller, Rudin, Sako, Hutter, 2024 -- "ANYmal Parkour: Learning Agile Navigation for Quadrupedal Robots," Science Robotics 9(88):eadi7566
Keywords: legged locomotion, quadruped, parkour, ANYmal, reinforcement learning, agile navigation, obstacle traversal

ETH Zurich's ANYmal robot was trained with a staged reinforcement-learning curriculum to jump gaps, climb obstacles taller than its own legs, and vault over barriers using onboard depth cameras for perception, all learned in simulation and transferred to hardware. It demonstrates that legged robots can acquire genuinely acrobatic, terrain-specific skills without hand-coded trajectories for each maneuver. The skills are still narrower than what a trained animal does; performance degrades on obstacle geometries well outside the simulated training distribution.

## Training thousands of robot simulations in parallel on one GPU cut locomotion training time from days to minutes
Source: Rudin, Hoeller, Reist, Hutter, 2022 -- "Learning to Walk in Minutes Using Massively Parallel Deep Reinforcement Learning," CoRL 2022, arXiv:2109.11978
Keywords: reinforcement learning, sim-to-real, quadruped, legged locomotion, GPU parallelization, Isaac Gym, training efficiency

By running thousands of quadruped simulation instances simultaneously on a single GPU (via NVIDIA's Isaac Gym), this work trained working locomotion policies in under 20 minutes on one workstation, versus hours or days on CPU clusters. That massive speedup made rapid iteration on reward design and terrain curricula practical and is now a standard tool across legged-robot labs. The result is an infrastructure advance, not a new locomotion behavior itself — quality of the learned gait still depends heavily on reward shaping.

## A transformer trained like a language model can predict humanoid walking, token by token
Source: Radosavovic, Zhang, Shi, Rajasegaran, Kamat, Darrell, Sreenath, Malik, 2024 -- "Humanoid Locomotion as Next Token Prediction," arXiv:2402.19469
Keywords: humanoid robot, bipedal locomotion, transformer, sequence modeling, sim-to-real, self-supervised learning

UC Berkeley researchers reframed humanoid control as sequence prediction: a causal transformer is trained to predict the next sensorimotor token from a mix of simulated trajectories, motion capture, and even YouTube videos of humans walking, some of which have no corresponding action labels. The resulting policy walked a full-size humanoid outdoors in San Francisco after training on only about 27 hours of real walking data, and generalized to unseen commands like walking backward. It's a striking demonstration that language-model-style training scales to embodied control, though the walking gait is still less robust than dedicated RL locomotion controllers on rough terrain.

## A quadruped agility benchmark quantifies how far robots still trail real animals
Source: Caluwaerts, Iscen, Kew, Yu et al. (Google DeepMind), 2023 -- "Barkour: Benchmarking Animal-level Agility with Quadruped Robots," arXiv:2305.14654
Keywords: quadruped, benchmark, agility, reinforcement learning, legged locomotion, sim-to-real, evaluation

Barkour is a standardized obstacle course (weave poles, jumps, a balance beam) plus a scoring formula that lets different quadruped control methods be compared on speed and agility the way dog agility trials work. The best learned policies in the paper reached roughly half of a trained dog's benchmark speed on the same course. Its value is mainly as a shared yardstick; the specific numeric scores are tied to one obstacle layout and may not transfer to judging agility on genuinely novel terrain.

## Reinforcement learning taught a robot hand to reorient objects using only a simulated hand and cameras
Source: OpenAI, Andrychowicz et al., 2018-2020 -- "Learning Dexterous In-Hand Manipulation," arXiv:1808.00177
Keywords: dexterous manipulation, in-hand manipulation, sim-to-real, domain randomization, reinforcement learning, Shadow Hand

OpenAI trained a policy entirely in simulation to reorient a cube-like object within a 24-degree-of-freedom Shadow robotic hand, using heavy domain randomization of physics parameters and camera images so the policy would transfer to the real hand without any real-world training. It was an early landmark showing sim-to-real transfer could work for genuinely high-dimensional dexterous manipulation, not just locomotion. The approach required enormous simulation compute (years of simulated experience) and the learned behavior, while robust to perturbations, was slower and less efficient than human finger dexterity.

## The same sim-to-real recipe scaled up to solving a Rubik's Cube one-handed
Source: OpenAI, Akkaya et al., 2019 -- "Solving Rubik's Cube with a Robot Hand," arXiv:1910.07113
Keywords: dexterous manipulation, sim-to-real, domain randomization, reinforcement learning, Shadow Hand, automatic domain randomization

Extending the Dactyl line of work, OpenAI added "automatic domain randomization" that progressively increases simulation difficulty as the policy improves, and used it to manipulate a Rubik's Cube to a solved state using a single robotic hand plus an external solver algorithm for the cube logic. The physical manipulation succeeded fully only about 20% of the time on the hardest scrambles, and the system was notably fragile to novel perturbations like a glove or a physical nudge not represented in training, illustrating a real limit of domain randomization rather than a full solution to robustness.

## A synthetic point-cloud dataset let a neural network plan robust grasps in under a second
Source: Mahler, Liang, Niyaz, Laskey, Doan, Liu, Ojea, Goldberg, 2017 -- "Dex-Net 2.0: Deep Learning to Plan Robust Grasps with Synthetic Point Clouds and Analytic Grasp Metrics," RSS 2017, arXiv:1703.09312
Keywords: grasping, grasp planning, Dex-Net, deep learning, point cloud, bin picking, GQ-CNN

UC Berkeley's Dex-Net 2.0 trained a Grasp Quality CNN on 6.7 million simulated grasps generated from thousands of 3D object models, scored by an analytic grasp-quality metric rather than real trials. On a real ABB YuMi arm it planned grasps in 0.8 seconds with a 93% success rate on adversarial-geometry objects it had never seen. It showed synthetic data alone, without any real robot experience, could produce grasp planners good enough for industrial use; performance drops on highly deformable, transparent, or reflective objects that violate the simulator's rigid-body, Lambertian-surface assumptions.

## Framing robot control as image "denoising" produces smoother, more reliable manipulation policies
Source: Chi, Feng, Du, Xu, Cousineau, Burchfiel, Song, 2023 -- "Diffusion Policy: Visuomotor Policy Learning via Action Diffusion," RSS 2023, arXiv:2303.04137
Keywords: imitation learning, learning from demonstration, diffusion model, visuomotor policy, robot manipulation, behavior cloning

Diffusion Policy represents a robot's action-generation process as a denoising diffusion model conditioned on camera images, rather than the standard single-shot regression used in behavior cloning. This handles multi-modal decisions gracefully (e.g., "grasp from the left or the right are both fine") and reduced compounding errors seen in earlier imitation-learning methods across dozens of manipulation tasks. It has become a widely adopted baseline; the tradeoff is slower inference since diffusion sampling requires multiple denoising steps per action, an active area of follow-up speedups.

## Randomizing a simulator's visual appearance let object-detection policies transfer to reality with zero real images
Source: Tobin, Fong, Ray, Schneider, Zaremba, Abbeel, 2017 -- "Domain Randomization for Transferring Deep Neural Networks from Simulation to the Real World," IROS 2017 (arXiv:1703.06907)
Keywords: sim-to-real, domain randomization, object detection, deep learning, simulation, transfer learning

Rather than trying to make a simulator photorealistic, this OpenAI/Berkeley paper randomized textures, lighting, camera position, and object colors across thousands of simulated scenes, forcing a detection network to learn features that hold up under any of them — including whatever the real world happens to look like. Trained purely on these randomized synthetic images, the network localized real objects for robotic grasping without ever seeing a real photo during training. Domain randomization has since become a default sim-to-real tool across robotics, though it needs a fairly wide, well-chosen randomization range or the "reality gap" is simply moved rather than closed.

## Fine-tuning a large vision-language model directly on robot actions gave it web-scale reasoning about physical tasks
Source: Brohan, Zitkovich, et al. (Google DeepMind), 2023 -- "RT-2: Vision-Language-Action Models Transfer Web Knowledge to Robotic Control," arXiv:2307.15818
Keywords: vision-language-action, VLA, RT-2, foundation model, robot manipulation, language-conditioned control, generalization

RT-2 fine-tuned large vision-language models (PaLI-X and PaLM-E) to output robot actions as text tokens, co-training on internet-scale image-caption data alongside real robot demonstrations. This let the robot follow instructions it had never been explicitly trained on, such as moving an object onto a picture of a specific number, by borrowing semantic knowledge from web pretraining. It's a genuine emergent-capability result on a real arm, but evaluations were done on a limited set of tasks in one lab kitchen environment, and the model requires a large cloud-hosted VLM backbone, which limits on-robot latency and deployment.

## A shared dataset of over a million robot demonstrations across 22 robot types enabled "generalist" manipulation policies
Source: Open X-Embodiment Collaboration (Google DeepMind + 20+ institutions), 2023 -- "Open X-Embodiment: Robotic Learning Datasets and RT-X Models," arXiv:2310.08864
Keywords: robot learning, dataset, generalist policy, RT-X, cross-embodiment, imitation learning, foundation model

This large academic-industry collaboration pooled over 60 existing robot datasets spanning 22 different robot embodiments into one standardized corpus, then showed that a single policy trained across all of them ("RT-X") generalized better to new robots and tasks than policies trained on any single robot's data alone. It established cross-embodiment training as a viable path toward general-purpose robot policies, similar to how large language models pool diverse text. The dataset remains uneven — some robot platforms and skills are represented by only a handful of trajectories, which can bias what the resulting generalist policy is actually good at.

## A single open-source SLAM library unified monocular, stereo, and multi-map visual-inertial mapping
Source: Campos, Elvira, Rodríguez, Montiel, Tardós, 2021 -- "ORB-SLAM3: An Accurate Open-Source Library for Visual, Visual-Inertial and Multi-Map SLAM," IEEE Transactions on Robotics, arXiv:2007.11898
Keywords: SLAM, visual-inertial odometry, mapping, localization, ORB-SLAM, multi-map, loop closure

ORB-SLAM3 combined feature-based visual tracking with tightly-integrated IMU fusion and a new multi-map system that can merge and reuse maps from earlier sessions, working across monocular, stereo, RGB-D, and fisheye cameras. It reported 2-5x better accuracy than prior open systems, reaching centimeter-level accuracy on standard drone and handheld benchmarks. It's one of the most widely deployed SLAM codebases in robotics research; like most feature-based SLAM, it can still struggle in low-texture environments (blank walls, glass) or highly dynamic scenes with lots of moving objects.

## Randomly growing a tree of reachable configurations solved motion planning in high-dimensional spaces
Source: LaValle, 1998 -- "Rapidly-Exploring Random Trees: A New Tool for Path Planning," Iowa State University TR 98-11 (foundational; refined in LaValle & Kuffner, 2001)
Keywords: motion planning, path planning, RRT, sampling-based planning, configuration space, robotics

RRT incrementally builds a tree by repeatedly sampling random points in a robot's configuration space and connecting each to its nearest existing tree node, which lets it explore high-dimensional spaces (many-jointed arms, cars with turning constraints) far faster than grid-search planners. It became foundational to almost all modern robot motion planning, later extended into RRT* which adds asymptotic optimality guarantees. The base algorithm produces jagged, non-optimal paths that typically need a smoothing or optimization post-processing step before execution on real hardware.

## Clipping policy updates gave reinforcement learning a simple, stable default algorithm
Source: Schulman, Wolski, Dhariwal, Radford, Klimov, 2017 -- "Proximal Policy Optimization Algorithms," arXiv:1707.06347
Keywords: reinforcement learning, PPO, policy gradient, robot learning, training stability, algorithm

PPO improves on earlier trust-region policy gradient methods by clipping how far a single update can push the policy away from its previous behavior, which is much simpler to implement than the constrained optimization used by TRPO while achieving comparable or better sample efficiency and stability. It is now the default reinforcement learning algorithm behind most legged-locomotion and dexterous-manipulation sim-to-real results in robotics. It is not the most sample-efficient algorithm class overall (off-policy methods can beat it in low-data regimes); its popularity in robotics comes largely from stability and ease of tuning at scale.

## Coupling electrostatic and hydraulic forces produced artificial muscles that self-heal after electrical breakdown
Source: Kellaris, Gopaluni Venkata, Smith, Mitchell, Keplinger, 2018 -- "Peano-HASEL Actuators / Hydraulically Amplified Self-Healing Electrostatic Actuators with Muscle-like Performance," Science 373(6501) lineage began with Science Robotics 3(14):eaar3276, 2018
Keywords: soft robotics, artificial muscle, HASEL, electrohydraulic actuator, self-healing, dielectric

HASEL actuators use a liquid dielectric sandwiched in a flexible pouch: applying voltage electrostatically squeezes the liquid to deform the pouch, generating linear or contractile motion, and because the liquid dielectric can flow back in and reseal after a local electrical breakdown, minor internal shorts don't permanently destroy the actuator the way they would a solid dielectric. This produces actuators approaching or exceeding natural muscle in strain and specific power without needing pneumatic compressors. Reliability under sustained high-cycle, high-humidity, real-world use (versus lab bench demos) is still an active open question for the technology.

## A soft, self-contained robotic fish swam untethered among real reef fish to study them without disturbing behavior
Source: Katzschmann, DelPreto, MacCurdy, Rus, 2018 -- "Exploration of Underwater Life with an Acoustically Controlled Soft Robotic Fish," Science Robotics 3(16):eaar3449
Keywords: soft robotics, underwater robot, bio-inspired, soft actuator, marine biology, acoustic control

MIT's "SoFi" uses a soft hydraulically actuated tail and adjustable side fins for buoyancy control, carries its own battery, camera, and acoustic communication receiver, and was field-tested swimming among real fish on a Fiji coral reef with a diver giving it acoustic depth and heading commands. It demonstrated that a soft-bodied swimmer could operate untethered in open water for extended dives (tens of minutes) without disrupting nearby marine life. Its swimming speed and maneuverability are still well below a comparably sized real fish, and the acoustic control link is short-range and line-of-sight limited underwater.

## A thousand simple robots self-assembled into arbitrary 2D shapes using only local sensing
Source: Rubenstein, Cornejo, Nagpal, 2014 -- "Programmable Self-Assembly in a Thousand-Robot Swarm," Science 345(6198):795-799
Keywords: swarm robotics, self-assembly, Kilobot, collective behavior, distributed algorithm, multi-robot systems

Harvard's Kilobot swarm of 1,024 coin-sized robots used only infrared neighbor-to-neighbor communication and local edge-following rules, no central controller or global map, to arrange themselves into pre-specified two-dimensional shapes like a star or a wrench. It was, at the time, by far the largest robot swarm demonstrated executing a coordinated task, proving simple local rules can produce complex global behavior at scale. A follow-up technical comment noted some completion-time and error-rate claims required specific interpretation, so exact performance numbers should be read from the original data rather than secondary summaries; the core self-assembly result itself is not disputed.

## Robots inspired by termite mound-building constructed 3D structures with no blueprint or central coordination
Source: Werfel, Petersen, Nagpal, 2014 -- "Designing Collective Behavior in a Termite-Inspired Robot Construction Team," Science 343(6172):754-758
Keywords: swarm robotics, collective construction, stigmergy, TERMES, multi-robot systems, distributed building

The TERMES robots each follow simple local rules — sense whether a brick is present nearby, decide whether to place or climb — reacting only to the current state of the structure itself (a coordination mechanism called stigmergy) rather than to each other directly or a shared plan. Using this, teams of robots built specified structures like towers and pyramids out of foam bricks without any leader or explicit task allocation. It's a compelling proof of concept for construction without centralized control, but it remains a lab-scale demonstration with custom bricks; scaling to full-size, real construction materials and outdoor conditions is unsolved.

## Thirty real drones flew as a collision-free flock using only onboard sensing, no central controller
Source: Vásárhelyi, Virágh, Somorjai, Nepusz, Eiben, Vicsek, 2018 -- "Optimized Flocking of Autonomous Drones in Confined Environments," Science Robotics 3(20):eaat3536
Keywords: swarm robotics, drone swarm, flocking, multi-robot systems, collision avoidance, decentralized control

This team used an evolutionary optimization algorithm to tune a decentralized flocking model, then flew 30 real quadcopters outdoors as a self-organized flock, avoiding both each other and obstacles with no central coordinator, which was among the largest such fully decentralized outdoor drone swarms reported at the time. Performance held up at surprisingly high drone speeds and around obstacles, showing decentralized flocking rules from biology transfer to real hardware limits. Communication delay and GPS noise still bound how densely such swarms can safely fly, and the demonstrated scale (tens, not hundreds, of drones) is smaller than swarms achieved indoors with motion-capture ground truth.

## A supervised autonomous robot outperformed human surgeons on stitching pig intestine back together
Source: Shademan, Decker, Opfermann, Leonard, Krieger, Kim, 2016 -- "Supervised Autonomous Robotic Soft Tissue Surgery," Science Translational Medicine 8(337):337ra64
Keywords: surgical robotics, medical robotics, STAR, autonomous surgery, suturing, laparoscopic

The Smart Tissue Autonomous Robot (STAR) used 3D and near-infrared fluorescent imaging plus force sensing to autonomously plan and execute sutures joining two segments of pig intestine (an anastomosis), producing more consistent, leak-resistant stitching than experienced surgeons doing the same procedure by hand or via standard laparoscopy in the same study. This was an early strong result for autonomy in actual soft-tissue surgery rather than rigid-structure tasks. The procedure was still supervised, with a human ready to intervene, and was performed on live pigs rather than humans — clinical translation to unsupervised human surgery has not been demonstrated.

## Large-scale analysis found robotic surgical systems fail mechanically in roughly 1% of procedures, rarely harming patients
Source: Systematic review and pooled analysis of da Vinci technical failures, 2025 -- World Journal of Urology (Springer)
Keywords: surgical robotics, da Vinci, robotic surgery, reliability, device malfunction, patient safety

Pooling data across roughly 3.3 million da Vinci-assisted procedures, this review found an overall device or instrument malfunction rate near 1%, with actual malfunction-related patient injuries occurring in only about 0.01% of cases — reassuringly low given the scale of adoption. It's a useful reality check against anecdotal "robot surgery gone wrong" stories, since the aggregate injury rate is small relative to overall surgical complication rates generally. The review is retrospective and pools heterogeneous procedure types and da Vinci generations, so it can't attribute failure causes to specific hardware versions or surgical specialties with precision.

## A camera pressed against a soft gel surface turned tiny surface deformations into high-resolution touch sensing
Source: Yuan, Dong, Adelson, 2017 -- "GelSight: High-Resolution Robot Tactile Sensors for Estimating Geometry and Force," Sensors 17(12):2762
Keywords: tactile sensing, GelSight, robot perception, touch sensor, grasping, vision-based tactile sensor

GelSight sensors use a small camera behind a soft, reflective elastomer skin: when the skin deforms against a touched surface, the camera images that deformation and converts it into a detailed 3D map of surface geometry plus estimated contact force, at a spatial resolution far beyond typical force-sensing resistors. This gave robots a way to "feel" fine surface texture and slip cheaply, using off-the-shelf camera hardware rather than exotic sensor arrays. It's become a standard tactile sensing platform for manipulation research; coverage area per sensor is small, so it works best on fingertips rather than whole-hand or whole-body touch sensing.

## A large annotated dataset from real warehouse operations exposed how hard bin picking still is at scale
Source: Amazon Robotics, ARMBench dataset paper, 2022 (ICRA 2023) -- "ARMBench: An Object-centric Benchmark Dataset for Robotic Manipulation"
Keywords: bin picking, industrial automation, warehouse robotics, dataset, benchmark, pick and place, perception

ARMBench collected images and outcome labels from an actual Amazon warehouse robotic picking system handling roughly 190,000 distinct product types, dwarfing prior bin-picking datasets that typically used a few hundred curated objects. It surfaced failure patterns — deformable packaging, transparent items, tangled clusters — that lab-scale grasp benchmarks with clean rigid objects simply don't capture. It's a valuable reality check on manipulation research maturity, though the dataset reflects one company's specific bins, grippers, and conveyor setup, limiting direct generalization to other warehouse hardware.

## A promptable image segmentation foundation model became a plug-in perception module for robot manipulation
Source: Kirillov, Mintun, Ravi, Mao, Rolland, Gustafson, et al. (Meta AI), 2023 -- "Segment Anything," arXiv:2304.02643
Keywords: perception, segmentation, foundation model, SAM, robot vision, zero-shot, grasp point detection

Segment Anything (SAM) was trained on over a billion masks to segment arbitrary objects in an image from a simple point or box prompt, without needing per-object training. Robotics researchers quickly adopted it as an off-the-shelf perception front-end — for example, prompting SAM with a rough click to get a clean object mask, then feeding that mask into a downstream grasp-point or manipulation planner. It generalizes remarkably well to novel object categories with no fine-tuning, but it has no notion of a scene's 3D geometry or physics, so downstream robotics work still needs separate depth or force reasoning layered on top.

## A robot hand copying human "postural synergies" grasped a wide range of objects with almost no active control
Source: Catalano, Grioli, Farnioli, Serio, Piazza, Bicchi, 2014 -- "Adaptive Synergies for the Design and Control of the Pisa/IIT SoftHand," International Journal of Robotics Research 33(5):768-782
Keywords: underactuated hand, robotic grasping, soft hand, adaptive synergies, tendon-driven, hand design

The Pisa/IIT SoftHand is driven by a single motor and one tendon routed through all its joints, mechanically encoding the dominant "postural synergy" patterns neuroscientists observed in human grasping, so the fingers passively conform around whatever object they touch. Despite having only one actuator, it robustly grasped a wide variety of everyday object shapes and survived being struck with a hammer without damage, demonstrating that mechanical intelligence in the hand itself can substitute for a lot of software-side control complexity. The tradeoff is precision: it can't do fine independent finger movements like pinching small parts, since all fingers are mechanically coupled together.

## An unpowered spring-and-clutch device cut the metabolic cost of walking without adding a motor
Source: Collins, Wiggin, Sawicki, 2015 -- "Reducing the Energy Cost of Human Walking Using an Unpowered Exoskeleton," Nature 522:212-215
Keywords: exoskeleton, biomechanics, metabolic cost, walking assistance, passive device, wearable robotics

This ankle exoskeleton uses a spring and mechanical clutch timed to the gait cycle, storing and releasing energy at the ankle without any motor or battery, and measured a 7% reduction in the metabolic energy cost of walking compared to walking without the device. That a purely passive, unpowered device could beat walking unassisted was a genuinely surprising result at the time, since most earlier exoskeletons made walking more, not less, metabolically costly. The benefit is specific to level, steady-state walking at one designed gait pattern; the device does not help (and can hinder) running, stairs, or highly variable terrain.

## Personalizing exoskeleton assistance in real-world walking improved speed and reduced energy use substantially more than fixed settings
Source: Slade, Kochenderfer, Delp, Collins, 2022 -- "Personalizing Exoskeleton Assistance While Walking in the Real World," Nature 610:277-282
Keywords: exoskeleton, personalization, machine learning, walking assistance, biomechanics, wearable robotics

Stanford researchers used a Bayesian optimization algorithm to tune a powered ankle exoskeleton's assistance profile individually for each person during roughly an hour of unstructured walking in an actual public setting, rather than a lab treadmill. Personalized users walked about 9% faster and used about 17% less energy per distance than in normal shoes, a bigger effect than most fixed-assistance exoskeleton studies report. The optimization currently takes real time to converge per person and per device, so this is not yet a plug-and-wear consumer product; it demonstrates the ceiling personalization can reach, not a deployed system.

## Studying how humans hand objects to each other produced timing rules that made robot handovers feel natural
Source: Strabala, Lee, Dragan, Forlizzi, Srinivasa, Cakmak, Micelli, 2013 -- "Toward Seamless Human-Robot Handovers," Journal of Human-Robot Interaction 2(1)
Keywords: human-robot interaction, HRI, object handover, robot manipulation, timing, collaboration

By observing structure in how humans coordinate handing objects to one another (approach, signal, transfer, release), this work derived a handover procedure for the HERB robot that could infer when and where a person wanted to receive an object and complete the transfer accordingly, succeeding in 83% of 70 handover trials. It remains one of the foundational HRI references for handover research, establishing timing and gaze/approach cues as the key variables. The 83% figure is specific to one robot, one set of objects, and lab conditions; it does not establish how handover success generalizes to cluttered, noisy, or safety-critical real environments.

## Real-time object detection made "look once, see everything" perception fast enough for robots
Source: Redmon, Divvala, Girshick, Farhadi, 2016 -- "You Only Look Once: Unified, Real-Time Object Detection," CVPR 2016, arXiv:1506.02640
Keywords: object detection, computer vision, YOLO, real-time perception, deep learning, robot vision

YOLO reframed object detection as a single neural network pass over the whole image predicting bounding boxes and classes directly, instead of the multi-stage region-proposal pipelines common before it, making detection fast enough to run at real-time video rates. That speed made it a practical default perception component for robots that need to react to moving objects or people, rather than just label static photos. Its main historical tradeoff versus slower two-stage detectors was lower accuracy on small or overlapping objects, though later YOLO versions substantially closed that gap.
