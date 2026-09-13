// Gazebo model plugin: change a traffic light's lens colors at runtime
// via a ROS topic.
//
// Gazebo Classic has no public API to change a spawned model's <visual>
// material. The stock LedPlugin does something similar but only on a
// fixed SDF-defined schedule, with no runtime control. gazebo_msgs/
// SetLightProperties (the standard ROS-Gazebo service) only changes
// <light> (illumination) - it does not touch a <visual>'s own material,
// so it can't make a lens sphere itself look colored/lit.
//
// This plugin does what LedPlugin does internally, but driven by a ROS
// topic instead of a schedule:
//   1) get each lens visual's numeric ID via Link::Visuals()
//   2) publish a gazebo::msgs::Visual with the updated material on the
//      "~/visual" transport topic
//
// Usage: publish "red" | "yellow" | "green" | "off" (std_msgs/String) on
// the topic named in <topic> (default /traffic_light/color).
//
// Adapted from SKKUAutoLab/H-Mobility-Autonomous-Advanced-Course-Simulation
// (GPL-2.0) - src/plugin_pkg/src/traffic_light_plugin.cpp - for this
// curriculum's traffic_light model (models/traffic_light/model.sdf),
// which uses one link per lens (red_light_link / yellow_light_link /
// green_light_link), matching that repo's traffic_ctrl model.

#include <chrono>
#include <map>
#include <memory>
#include <string>

#include <gazebo/common/Plugin.hh>
#include <gazebo/msgs/msgs.hh>
#include <gazebo/physics/physics.hh>
#include <gazebo/transport/transport.hh>

#include <gazebo_ros/node.hpp>
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>

namespace gazebo
{

class TrafficLightPlugin : public ModelPlugin
{
public:
  void Load(physics::ModelPtr model, sdf::ElementPtr sdf) override
  {
    this->model_ = model;

    // lens name -> (link name, full-brightness color when on)
    this->lenses_ = {
      {"red", {"red_light_link", ignition::math::Color(1.0, 0.0, 0.0, 1.0)}},
      {"yellow", {"yellow_light_link", ignition::math::Color(1.0, 0.85, 0.0, 1.0)}},
      {"green", {"green_light_link", ignition::math::Color(0.0, 1.0, 0.0, 1.0)}},
    };

    // Gazebo transport - the channel that actually repaints the lens.
    this->gz_node_ = transport::NodePtr(new transport::Node());
    this->gz_node_->Init(model->GetWorld()->Name());
    this->visual_pub_ = this->gz_node_->Advertise<msgs::Visual>("~/visual");

    this->ros_node_ = gazebo_ros::Node::Get(sdf);

    std::string topic = "/traffic_light/color";
    if (sdf->HasElement("topic")) {
      topic = sdf->Get<std::string>("topic");
    }

    this->sub_ = this->ros_node_->create_subscription<std_msgs::msg::String>(
      topic, 10,
      [this](const std_msgs::msg::String::SharedPtr msg) { this->SetColor(msg->data); });

    std::string initial = sdf->HasElement("initial_color")
      ? sdf->Get<std::string>("initial_color")
      : "red";

    RCLCPP_INFO(
      this->ros_node_->get_logger(),
      "traffic_light_plugin ready (topic: %s, initial color: %s)",
      topic.c_str(), initial.c_str());

    this->state_ = initial;

    // Visual-update messages can be silently dropped if the renderer
    // isn't ready yet or the queue is backed up, leaving two lenses lit
    // or all of them dark. Re-apply the current state periodically so
    // it self-heals instead of staying stuck.
    this->timer_ = this->ros_node_->create_wall_timer(
      std::chrono::milliseconds(1000),
      [this]() { this->Apply(this->state_); });
  }

private:
  struct Lens
  {
    std::string link;
    ignition::math::Color color;
  };

  /// Called when a color change request arrives on the topic.
  void SetColor(const std::string & state)
  {
    if (this->lenses_.find(state) == this->lenses_.end() && state != "off") {
      RCLCPP_WARN(this->ros_node_->get_logger(), "unknown color: %s", state.c_str());
      return;
    }
    this->state_ = state;
    this->Apply(state);
    RCLCPP_INFO(this->ros_node_->get_logger(), "traffic_light -> %s", state.c_str());
  }

  /// Turn on only the requested lens, turn off the rest. Also called
  /// periodically to re-apply the current state.
  ///
  /// Order matters: turn off everything that should be off first, then
  /// turn on the requested one last, so it reads as an instant switch
  /// instead of a brief moment with everything lit or everything dark.
  void Apply(const std::string & state)
  {
    for (const auto & entry : this->lenses_) {
      if (entry.first == state) {
        continue;
      }
      this->Paint(entry.second.link, entry.first, ignition::math::Color::Black, false);
    }

    auto it = this->lenses_.find(state);
    if (it != this->lenses_.end()) {
      this->Paint(it->second.link, it->first, it->second.color, true);
    }
  }

  /// Turn one lens on or off.
  ///
  /// Publishing a message with only a couple of fields set is ignored
  /// by gzclient - it needs the full original visual message (as
  /// LedSetting does), copied and re-sent with just the color changed.
  void Paint(
    const std::string & link_name, const std::string & visual_name,
    const ignition::math::Color & color, bool on)
  {
    physics::LinkPtr link = this->model_->GetLink(link_name);
    if (!link) {
      RCLCPP_WARN(this->ros_node_->get_logger(), "link not found: %s", link_name.c_str());
      return;
    }

    ignition::math::Color dim(color.R() * 0.15, color.G() * 0.15, color.B() * 0.15, 1.0);
    int count = 0;

    for (const auto & entry : link->Visuals()) {
      msgs::Visual msg = entry.second;
      msg.set_id(entry.first);
      msg.set_parent_name(link->GetScopedName());
      msg.set_parent_id(link->GetId());

      msgs::Set(msg.mutable_material()->mutable_emissive(), color);
      msgs::Set(msg.mutable_material()->mutable_ambient(), dim);
      msgs::Set(msg.mutable_material()->mutable_diffuse(), dim);

      // Color alone doesn't read as "off" - hide the off lenses outright.
      msg.set_transparency(on ? 0.0 : 1.0);
      msg.set_visible(on);

      // Blocking publish (2nd arg true) waits for each send and makes
      // switching visibly laggy. Fire-and-forget instead; the periodic
      // re-apply above covers any message that gets dropped.
      this->visual_pub_->Publish(msg);
      ++count;
    }

    if (count == 0) {
      RCLCPP_WARN(
        this->ros_node_->get_logger(), "no visuals found on link: %s", link_name.c_str());
      return;
    }

    RCLCPP_DEBUG(
      this->ros_node_->get_logger(), "  %s %s (%d visual(s))",
      visual_name.c_str(), on ? "ON" : "off", count);
  }

  physics::ModelPtr model_;
  std::map<std::string, Lens> lenses_;
  std::string state_{"red"};

  transport::NodePtr gz_node_;
  transport::PublisherPtr visual_pub_;

  gazebo_ros::Node::SharedPtr ros_node_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr sub_;
  rclcpp::TimerBase::SharedPtr timer_;
};

GZ_REGISTER_MODEL_PLUGIN(TrafficLightPlugin)

}  // namespace gazebo
