"""Generate an Ignition Gazebo (Fortress) world for one twin scenario.

The world has a soil field with crop beds, the robot and the people of the scenario.
- The robot is a box with cosmetic wheels. It is moved by `VelocityControl` from the
  ZLAC bridge model in `gz_twin_node.py`, and it carries a `gpu_lidar` mounted with 180 deg
  yaw like the real one (`/scan`, 720 samples, 0.05-12 m, 10 Hz).
- People are a cylinder body plus a sphere head (radius `PERSON_RADIUS_M`), driven along
  the scenario waypoints by `gz_twin_node.py`. They have no collision, so they never push
  the robot. The LiDAR still sees them because `gpu_lidar` hits visuals.
- Crop beds sit beside the walking lane (|y| >= 1.4 m). They are outside the LiDAR
  sectorizer's ±15 deg window along the lane.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from sim.twin.scenarios import SCENARIOS
from sim.twin.world import PERSON_RADIUS_M

COLORS = {"target": "0.85 0.15 0.15 1", "distractor": "0.15 0.35 0.85 1"}


def person(name: str, x: float, y: float) -> str:
    color = COLORS.get(name, "0.9 0.6 0.1 1")
    return f"""
  <model name="{name}"><pose>{x} {y} 0 0 0 0</pose>
    <link name="body"><gravity>false</gravity>
      <visual name="torso"><pose>0 0 0.95 0 0 0</pose><geometry><cylinder><radius>{PERSON_RADIUS_M}</radius><length>1.3</length></cylinder></geometry>
        <material><diffuse>{color}</diffuse><ambient>{color}</ambient></material></visual>
      <visual name="head"><pose>0 0 1.75 0 0 0</pose><geometry><sphere><radius>0.13</radius></sphere></geometry>
        <material><diffuse>0.95 0.8 0.65 1</diffuse><ambient>0.95 0.8 0.65 1</ambient></material></visual>
      <visual name="legs"><pose>0 0 0.25 0 0 0</pose><geometry><cylinder><radius>{PERSON_RADIUS_M * 0.8}</radius><length>0.5</length></cylinder></geometry>
        <material><diffuse>0.15 0.15 0.2 1</diffuse><ambient>0.15 0.15 0.2 1</ambient></material></visual>
    </link>
    <plugin filename="ignition-gazebo-velocity-control-system" name="ignition::gazebo::systems::VelocityControl"/>
  </model>"""


def crop_beds() -> str:
    beds = []
    for i, y in enumerate((-3.2, -2.0, 2.0, 3.2)):
        beds.append(f"""
  <model name="bed_{i}"><static>true</static><pose>5 {y} 0.1 0 0 0</pose><link name="l">
    <visual name="soil"><geometry><box><size>14 0.8 0.2</size></box></geometry>
      <material><diffuse>0.35 0.22 0.12 1</diffuse><ambient>0.35 0.22 0.12 1</ambient></material></visual>""")
        for k in range(14):
            beds.append(f"""
    <visual name="plant_{k}"><pose>{-6.5 + k} 0 0.25 0 0 0</pose><geometry><sphere><radius>0.25</radius></sphere></geometry>
      <material><diffuse>0.2 0.6 0.2 1</diffuse><ambient>0.2 0.6 0.2 1</ambient></material></visual>""")
        beds.append("</link></model>")
    return "".join(beds)


def robot() -> str:
    wheels = "".join(
        f"""<visual name="wheel_{n}"><pose>{x} {y} -0.05 1.5708 0 0</pose><geometry><cylinder><radius>0.085</radius><length>0.06</length></cylinder></geometry>
        <material><diffuse>0.1 0.1 0.1 1</diffuse><ambient>0.1 0.1 0.1 1</ambient></material></visual>"""
        for n, x, y in (("fl", 0.15, 0.23), ("fr", 0.15, -0.23), ("rl", -0.15, 0.23), ("rr", -0.15, -0.23)))
    return f"""
  <model name="robot"><pose>0 0 0.13 0 0 0</pose>
    <link name="base"><gravity>false</gravity>
      <visual name="chassis"><geometry><box><size>0.5 0.4 0.15</size></box></geometry>
        <material><diffuse>0.95 0.75 0.1 1</diffuse><ambient>0.95 0.75 0.1 1</ambient></material></visual>
      <visual name="mast"><pose>-0.1 0 0.25 0 0 0</pose><geometry><cylinder><radius>0.03</radius><length>0.35</length></cylinder></geometry>
        <material><diffuse>0.3 0.3 0.3 1</diffuse></material></visual>
      <visual name="camera"><pose>0.2 0 0.42 0 0 0</pose><geometry><box><size>0.05 0.1 0.04</size></box></geometry>
        <material><diffuse>0.05 0.05 0.05 1</diffuse></material></visual>
      {wheels}
      <sensor name="lidar" type="gpu_lidar"><pose>0 0 0.12 0 0 {math.pi}</pose><topic>scan</topic><update_rate>10</update_rate>
        <ray><scan><horizontal><samples>720</samples><resolution>1</resolution>
          <min_angle>{-math.pi}</min_angle><max_angle>{math.pi - 2 * math.pi / 720}</max_angle></horizontal></scan>
          <range><min>0.05</min><max>12</max></range>
          <noise><type>gaussian</type><mean>0</mean><stddev>0.01</stddev></noise></ray>
        <always_on>1</always_on><visualize>true</visualize></sensor>
    </link>
    <plugin filename="ignition-gazebo-velocity-control-system" name="ignition::gazebo::systems::VelocityControl"/>
  </model>"""


def gui(camera_pose: str) -> str:
    return f"""
  <gui fullscreen="0">
    <plugin filename="GzScene3D" name="3D View">
      <ignition-gui><title>3D View</title><property type="bool" key="showTitleBar">false</property>
        <property type="string" key="state">docked</property></ignition-gui>
      <engine>ogre2</engine><scene>scene</scene>
      <ambient_light>0.5 0.5 0.5</ambient_light><background_color>0.7 0.8 0.95</background_color>
      <camera_pose>{camera_pose}</camera_pose>
    </plugin>
  </gui>"""


def world(scenario: str, camera_pose: str) -> str:
    spec = SCENARIOS[scenario]
    people = "".join(person(n, wp[0][1], wp[0][2]) for n, _, wp in spec["people"])
    return f"""<?xml version="1.0"?>
<!-- Generated by sim/gazebo/world_gen.py for scenario '{scenario}'. Do not edit. -->
<sdf version="1.8">
<world name="farm">
  <physics name="4ms" type="ignored"><max_step_size>0.004</max_step_size><real_time_factor>1.0</real_time_factor></physics>
  <plugin filename="ignition-gazebo-physics-system" name="ignition::gazebo::systems::Physics"/>
  <plugin filename="ignition-gazebo-user-commands-system" name="ignition::gazebo::systems::UserCommands"/>
  <plugin filename="ignition-gazebo-scene-broadcaster-system" name="ignition::gazebo::systems::SceneBroadcaster"/>
  <plugin filename="ignition-gazebo-sensors-system" name="ignition::gazebo::systems::Sensors"><render_engine>ogre2</render_engine></plugin>
  <scene><ambient>0.6 0.6 0.6 1</ambient><background>0.7 0.8 0.95 1</background><grid>false</grid></scene>
  <light type="directional" name="sun"><cast_shadows>true</cast_shadows><pose>0 0 10 0 0 0</pose>
    <diffuse>0.9 0.9 0.85 1</diffuse><specular>0.2 0.2 0.2 1</specular><direction>-0.4 0.3 -0.9</direction></light>
  <model name="ground"><static>true</static><link name="l">
    <collision name="c"><geometry><plane><normal>0 0 1</normal><size>60 60</size></plane></geometry></collision>
    <visual name="v"><geometry><plane><normal>0 0 1</normal><size>60 60</size></plane></geometry>
      <material><diffuse>0.62 0.52 0.36 1</diffuse><ambient>0.62 0.52 0.36 1</ambient></material></visual></link></model>
  {crop_beds()}
  {robot()}
  {people}
  {gui(camera_pose)}
</world>
</sdf>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", choices=sorted(SCENARIOS))
    ap.add_argument("out", type=Path)
    ap.add_argument("--camera-pose", default="-3.5 -5.5 4.5 0 0.5 0.75")
    args = ap.parse_args()
    args.out.write_text(world(args.scenario, args.camera_pose), encoding="utf-8")


if __name__ == "__main__":
    main()
