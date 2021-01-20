import copy

import numpy
import rospy
import walknet_curvewalking_project.phantomx.RobotSettings as RSTATIC
import tf.transformations as transformations
from visualization_msgs.msg import Marker
from geometry_msgs.msg import Point
from std_msgs.msg import Float64
from math import sin, cos, atan2, pow, pi, acos, radians

from walknet_curvewalking_project.support.constants import CONTROLLER_FREQUENCY


class SingleLeg:

    def __init__(self, name, segment_lengths, tf_listener, movement_dir):
        self.name = name
        self.tf_listener = tf_listener
        self.alpha_pub = rospy.Publisher('/phantomx/j_c1_' + self.name + '_position_controller/command', Float64,
            queue_size=1)
        self.beta_pub = rospy.Publisher('/phantomx/j_thigh_' + self.name + '_position_controller/command', Float64,
            queue_size=1)
        self.gamma_pub = rospy.Publisher('/phantomx/j_tibia_' + self.name + '_position_controller/command', Float64,
            queue_size=1)

        self.alpha = None
        self.beta = None
        self.gamma = None
        self.c1_static_transform = RSTATIC.body_c1_tf[RSTATIC.leg_names.index(self.name)]

        self.alpha_target = None
        self.beta_target = None
        self.gamma_target = None

        self.alpha_reached = True
        self.beta_reached = True
        self.gamma_reached = True

        self.segment_lengths = segment_lengths
        self.movement_dir = movement_dir
        # self.rotation_dir = rotation_dir

        self.ee_pos = None

        self.visualization_pub = rospy.Publisher('/kinematics', Marker, queue_size=1)
        self.c1_ee_points = Marker()
        self.global_ee_points = Marker()
        self.c1_leg_vec_lines = Marker()
        self.global_leg_vec_lines = Marker()
        self.set_up_visualization()

    def set_up_visualization(self):
        self.global_ee_points.header.frame_id = self.global_leg_vec_lines.header.frame_id = "MP_BODY"
        self.c1_ee_points.header.frame_id = self.c1_leg_vec_lines.header.frame_id = "c1_" + self.name
        # self.c1_ee_points.header.frame_id = self.c1_leg_vec_lines.header.frame_id = "MP_BODY"
        self.c1_ee_points.header.stamp = self.global_ee_points.header.stamp = self.global_leg_vec_lines.header.stamp = \
            self.c1_leg_vec_lines.header.stamp = rospy.Time.now()
        self.c1_ee_points.ns = self.global_ee_points.ns = self.global_leg_vec_lines.ns = self.c1_leg_vec_lines.ns = \
            "points_and_lines"
        self.c1_ee_points.action = self.global_ee_points.action = self.global_leg_vec_lines.action = \
            self.c1_leg_vec_lines.action = Marker.ADD
        self.c1_ee_points.pose.orientation.w = self.global_ee_points.pose.orientation.w = self.global_leg_vec_lines.pose.orientation.w = \
            self.c1_leg_vec_lines.pose.orientation.w = 1.0

        self.global_ee_points.id = 0
        self.c1_ee_points.id = 1
        self.global_leg_vec_lines.id = 2
        self.c1_leg_vec_lines.id = 3

        self.global_ee_points.type = Marker.POINTS
        self.c1_ee_points.type = Marker.POINTS
        self.global_leg_vec_lines.type = Marker.LINE_LIST
        self.c1_leg_vec_lines.type = Marker.LINE_LIST

        self.global_ee_points.scale.x = 0.005
        self.global_ee_points.scale.y = 0.005
        self.c1_ee_points.scale.x = 0.005
        self.c1_ee_points.scale.y = 0.005

        self.global_leg_vec_lines.scale.x = 0.0025
        self.c1_leg_vec_lines.scale.x = 0.0025

        self.global_ee_points.color.r = 1.0
        self.global_ee_points.color.a = 1.0
        self.c1_ee_points.color.b = 1.0
        self.c1_ee_points.color.a = 1.0
        self.global_leg_vec_lines.color.a = 1.0
        self.c1_leg_vec_lines.color.a = 1.0
        self.global_leg_vec_lines.color.r = 1.0
        self.c1_leg_vec_lines.color.b = 1.0

    def pub_local(self):
        start_point = Point()
        start = [0, 0, 0]
        start_point.x = start[0]
        start_point.y = start[1]
        start_point.z = start[2]
        vecs = self.c1_rotation(-self.alpha, self.compute_forward_kinematics_c1())
        pos = Point()
        pos.x = start_point.x + vecs[0]
        pos.y = start_point.y + vecs[1]
        pos.z = start_point.z + vecs[2]
        self.c1_ee_points.points.append(start_point)
        self.c1_ee_points.points.append(pos)
        self.c1_leg_vec_lines.points.append(start_point)
        self.c1_leg_vec_lines.points.append(pos)

        rate = rospy.Rate(CONTROLLER_FREQUENCY)
        for i in range(0, 5):
            self.visualization_pub.publish(self.c1_ee_points)
            self.visualization_pub.publish(self.c1_leg_vec_lines)
            rate.sleep()

    def pub_global(self):
        start_point = Point()
        start = [0, 0, 0]
        start_point.x = start[0]
        start_point.y = start[1]
        start_point.z = start[2]
        self.global_ee_points.points.append(start_point)
        vecs = self.compute_forward_kinematics()
        pos = Point()
        pos.x = start_point.x + vecs[0]
        pos.y = start_point.y + vecs[1]
        pos.z = start_point.z + vecs[2]
        self.global_ee_points.points.append(pos)
        self.global_leg_vec_lines.points.append(start_point)
        self.global_leg_vec_lines.points.append(pos)

        rate = rospy.Rate(CONTROLLER_FREQUENCY)
        for i in range(0, 5):
            self.visualization_pub.publish(self.global_ee_points)
            self.visualization_pub.publish(self.global_leg_vec_lines)
            rate.sleep()

    def is_ready(self):
        if self.alpha is not None and self.beta is not None and self.gamma is not None:
            return True
        else:
            return False

    def c1_callback(self, data):
        self.alpha = data.process_value
        self.alpha_target = data.set_point
        if data.error < 0.01:
            self.alpha_reached = True
        else:
            self.alpha_reached = False

    def thigh_callback(self, data):
        self.beta = data.process_value
        self.beta_target = data.set_point
        if data.error < 0.01:
            self.beta_reached = True
        else:
            self.beta_reached = False

    def tibia_callback(self, data):
        self.gamma = data.process_value
        self.gamma_target = data.set_point
        if data.error < 0.01:
            self.gamma_reached = True
        else:
            self.gamma_reached = False

    def ee_position(self):
        self.update_ee_position()
        return self.ee_pos[0:3]

    def update_ee_position(self):
        self.ee_pos = self.compute_forward_kinematics()

    def target_reached(self):
        return self.alpha_reached and self.beta_reached and self.gamma_reached

    ##
    #   Estimate ground ground_contact:
    #   Predict current leg position (using fw kinematics) and
    #   simply decide if the leg should touch ground
    #   (very stable, but works only on flat terrain).
    def predictedGroundContact(self):
        if self.name == "lf" or self.name == "rf":
            if (self.ee_position()[2] < (RSTATIC.front_initial_aep[2] * RSTATIC.predicted_ground_contact_height_factor)) \
                    and abs(self.ee_position()[0] + self.movement_dir * RSTATIC.front_initial_aep[0]) < 0.025:
                rospy.loginfo("predict ground contact for front leg")
                return 1
        if self.name == "lm" or self.name == "rm":
            if (self.ee_position()[2] < (
                    RSTATIC.middle_initial_aep[2] * RSTATIC.predicted_ground_contact_height_factor)) \
                    and abs(self.ee_position()[0] + self.movement_dir * RSTATIC.middle_initial_aep[0]) < 0.025:
                rospy.loginfo("predict ground contact for middle leg")
                return 1
        if self.name == "lr" or self.name == "rr":
            if (self.ee_position()[2] < (RSTATIC.hind_initial_aep[2] * RSTATIC.predicted_ground_contact_height_factor)) \
                    and abs(self.ee_position()[0] + self.movement_dir * RSTATIC.hind_initial_aep[0]) < 0.025:
                rospy.loginfo("predict ground contact for rear leg")
                return 1

        return 0

    # compute ee_position based on current joint values in c1 coordinate frame (= leg coordinate frame)
    # code from https://www.programcreek.com/python/example/96799/tf.transformations
    def compute_forward_kinematics_tf(self):
        if not self.is_ready():
            rospy.loginfo("haven't received Joint values yet! skipp")
            return
        (trans, rot) = self.tf_listener.lookupTransform('MP_BODY', 'tibia_' + self.name, rospy.Time(0))
        # (trans, rot) = self.tf_listener.lookupTransform('MP_BODY', 'tibia_' + self.name, rospy.Time(0))
        pos = numpy.array(transformations.quaternion_matrix(rot))
        pos[0, 3] = trans[0]
        pos[1, 3] = trans[1]
        pos[2, 3] = trans[2]
        return numpy.array(numpy.dot(pos, [0, 0, 0.13, 1]))
        # return numpy.array(numpy.dot(pos, [0, 0, 0, 1]))

    def check_joint_ranges(self, angles):
        return angles[0] >= -0.6 or angles[0] <= 0.6 or angles[1] >= -1.0 or angles[1] <= 0.3 or angles[2] >= -1.0 or \
               angles[2] <= 1.0

    # ee position in body frame
    def compute_forward_kinematics(self, angles=None):
        if angles is None:
            return self.apply_c1_static_transform(self.compute_forward_kinematics_c1())
        else:
            return self.apply_c1_static_transform(self.compute_forward_kinematics_c1(angles))

    def compute_forward_kinematics_c1(self, angles=None):
        if angles is None:
            alpha = self.alpha
            beta = self.beta
            gamma = self.gamma
        elif self.check_joint_ranges(angles):
            alpha = angles[0]
            beta = angles[1]
            gamma = angles[2]
        else:
            raise Exception(
                'The provided angles for ' + self.name + '(' + str(angles[0]) + ', ' + str(angles[1]) + ', ' + str(
                    angles[2]) + ') are not valid for the forward/inverse kinematics.')

        temp_tarsus_position = self.c1_rotation(alpha, self.c1_thigh_transformation(beta,
            self.thigh_tibia_transformation(gamma, self.tibia_ee_transformation())))
        # calculate shoulder angle as angle of vector from c1 pos to ee pos in body frame
        x_pos = -temp_tarsus_position[1]
        y_pos = temp_tarsus_position[2]

        alpha_check = -atan2(y_pos, x_pos)
        if abs(alpha_check - alpha) >= 0.01:
            raise Exception('The provided angles for ' + self.name + '(' + str(alpha) + ', ' + str(beta) + ', ' + str(
                gamma) + ') are not valid for the forward/inverse kinematics.')
        return temp_tarsus_position

    def c1_rotation(self, alpha, point=numpy.array([0, 0, 0, 1])):
        # point=numpy.append(point,1)
        # TODO ist alpha reversed?
        # alpha *= -1  # The direction of alpha is reversed as compared to the denavit-hartenberg notation.
        # left legs:
        cos_alpha = cos(alpha)
        sin_alpha = sin(alpha)
        # if self.movement_dir == -1:
        #    cos_alpha = cos(alpha + radians(180))
        #    sin_alpha = sin(alpha + radians(180))
        cos90 = cos(radians(0))
        sin90 = sin(radians(0))
        trans = numpy.array([(cos90, sin_alpha * sin90, cos_alpha * sin90, 0),
            (0, cos_alpha, 0 - sin_alpha, 0),
            (0 - sin90, sin_alpha * cos90, cos_alpha * cos90, 0),
            (0, 0, 0, 1)])
        # print('trans: ', trans)
        return trans.dot(point)

    def body_leg_transformation(self, point=numpy.array([0, 0, 0, 1])):
        # point=numpy.append(point,1)
        # TODO ist alpha reversed?
        # alpha *= -1  # The direction of alpha is reversed as compared to the denavit-hartenberg notation.
        trans = numpy.array([(1, 0, 0, 0),
            (0, 1, 0, 0.1034),
            (0, 0, 1, 0.001116),
            (0, 0, 0, 1)])
        # print('trans: ', trans)
        return trans.dot(point)

    def leg_c1_transformation(self, alpha, point=numpy.array([0, 0, 0, 1])):
        # point=numpy.append(point,1)
        # TODO ist alpha reversed?
        # alpha *= -1  # The direction of alpha is reversed as compared to the denavit-hartenberg notation.
        cos_alpha = cos(alpha + radians(180))
        sin_alpha = sin(alpha + radians(180))
        cos90 = cos(radians(-90))
        sin90 = sin(radians(-90))
        trans = numpy.array([(cos90, sin_alpha * sin90, cos_alpha * sin90, 0),
            (0, cos_alpha, 0 - sin_alpha, 0),
            (0 - sin90, sin_alpha * cos90, cos_alpha * cos90, 0),
            (0, 0, 0, 1)])
        # print('trans: ', trans)
        return trans.dot(point)

    def c1_thigh_transformation(self, beta, point=numpy.array([0, 0, 0, 1])):
        # point=numpy.append(point,1)
        # TODO ist alpha reversed?
        # alpha *= -1  # The direction of alpha is reversed as compared to the denavit-hartenberg notation.
        cos_alpha = cos(beta)
        sin_alpha = sin(beta)
        # TODO rotate by 90 degrees only for left legs?
        cos90 = cos(radians(90))
        sin90 = sin(radians(90))
        trans = numpy.array([(cos90, sin_alpha * sin90, cos_alpha * sin90, 0),
            (0, cos_alpha, 0 - sin_alpha, -0.054),  # TODO - only for left legs?
            (0 - sin90, sin_alpha * cos90, cos_alpha * cos90, 0),
            (0, 0, 0, 1)])
        # print('trans: ', trans)
        return trans.dot(point)

    def thigh_tibia_transformation(self, gamma, point=numpy.array([0, 0, 0, 1])):
        # point=numpy.append(point,1)
        # TODO ist alpha reversed?
        # alpha *= -1  # The direction of alpha is reversed as compared to the denavit-hartenberg notation.
        cos_alpha = cos(gamma)
        sin_alpha = sin(gamma)
        cos90 = cos(radians(180))
        sin90 = sin(radians(180))
        trans = numpy.array([(cos90, sin_alpha * sin90, cos_alpha * sin90, 0),
            (0, cos_alpha, 0 - sin_alpha, -0.0645),
            (0 - sin90, sin_alpha * cos90, cos_alpha * cos90, -0.0145),
            (0, 0, 0, 1)])
        # print('trans: ', trans)
        return trans.dot(point)

    def tibia_ee_transformation(self, point=numpy.array([0, 0, 0, 1])):
        # point=numpy.append(point,1)
        # TODO ist alpha reversed?
        # alpha *= -1  # The direction of alpha is reversed as compared to the denavit-hartenberg notation.
        trans = numpy.array([(1, 0, 0, 0),
            (0, 1, 0, -0.16),
            (0, 0, 1, 0.02),
            (0, 0, 0, 1)])
        # print('trans: ', trans)
        return trans.dot(point)

    def body_c1_transform(self, point=[0, 0, 0, 1]):
        # (trans, rot) = self.tf_listener.lookupTransform('MP_BODY', 'thigh_' + self.name, rospy.Time(0))
        (trans, rot) = self.tf_listener.lookupTransform('MP_BODY', 'c1_' + self.name, rospy.Time(0))
        pos = numpy.array(transformations.quaternion_matrix(rot))
        pos[0, 3] = trans[0]
        pos[1, 3] = trans[1]
        pos[2, 3] = trans[2]
        return numpy.array(numpy.dot(pos, self.c1_rotation(-self.alpha, point)))
        # return numpy.array(numpy.dot(pos, point))

    def apply_c1_static_transform(self, point=[0, 0, 0, 1]):
        return numpy.array(numpy.dot(self.c1_static_transform, point))

    # code from https://www.programcreek.com/python/example/96799/tf.transformations
    def alpha_forward_kinematics(self, point=[0, 0, 0, 1]):
        # (trans, rot) = self.tf_listener.lookupTransform('MP_BODY', 'thigh_' + self.name, rospy.Time(0))
        (trans, rot) = self.tf_listener.lookupTransform('c1_' + self.name, 'thigh_' + self.name, rospy.Time(0))
        pos = numpy.array(transformations.quaternion_matrix(rot))
        pos[0, 3] = trans[0]
        pos[1, 3] = trans[1]
        pos[2, 3] = trans[2]
        return numpy.array(numpy.dot(pos, point))

    # code from https://www.programcreek.com/python/example/96799/tf.transformations
    def beta_forward_kinematics(self, point=[0, 0, 0, 1]):
        (trans, rot) = self.tf_listener.lookupTransform('thigh_' + self.name, 'tibia_' + self.name, rospy.Time(0))
        pos = numpy.array(transformations.quaternion_matrix(rot))
        pos[0, 3] = trans[0]
        pos[1, 3] = trans[1]
        pos[2, 3] = trans[2]
        return numpy.array(numpy.dot(pos, point))

    #  Calculation of inverse kinematics for a leg:
    #   Given a position in 3D space a joint configuration is calculated.
    #   When no position is provided the current position of the current leg is used
    #   to calculate the complementing angles.
    #   @param p point in body coordinate system
    def compute_inverse_kinematics(self, p=None):
        if isinstance(p, (type(None))):
            p = self.ee_position()
        if len(p) == 3:
            p = numpy.append(p, [1])
        p_temp = copy.copy(p)

        # c1_pos = self.body_c1_transformation(self.alpha)
        c1_pos = self.apply_c1_static_transform()
        # alpha_angle: float = -atan2(p[1], (p[0]))
        # switched x and y coordination because the leg points in the direction of the y axis of the MP_BODY frame:
        c1_static_rotation_inverse = numpy.array([
            [self.c1_static_transform[0][0], self.c1_static_transform[1][0], self.c1_static_transform[2][0]],
            [self.c1_static_transform[0][1], self.c1_static_transform[1][1], self.c1_static_transform[2][1]],
            [self.c1_static_transform[0][2], self.c1_static_transform[1][2], self.c1_static_transform[2][2]]])
        translation_inverse = numpy.array(numpy.dot(-c1_static_rotation_inverse,
            [self.c1_static_transform[0][3], self.c1_static_transform[1][3], self.c1_static_transform[2][3]]))
        c1_static_inverse = numpy.array([
            [c1_static_rotation_inverse[0][0], c1_static_rotation_inverse[0][1], c1_static_rotation_inverse[0][2],
                translation_inverse[0]],
            [c1_static_rotation_inverse[1][0], c1_static_rotation_inverse[1][1], c1_static_rotation_inverse[1][2],
                translation_inverse[1]],
            [c1_static_rotation_inverse[2][0], c1_static_rotation_inverse[2][1], c1_static_rotation_inverse[2][2],
                translation_inverse[2]],
            [0, 0, 0, 1]])
        p_c1 = numpy.array(numpy.dot(c1_static_inverse, p))
        alpha_angle = -atan2(p_c1[2], -p_c1[1])

        beta_pos = self.c1_rotation(alpha_angle, self.c1_thigh_transformation(0))
        lct = numpy.linalg.norm(p[0:3] - self.apply_c1_static_transform(beta_pos)[0:3])

        default_gamma_pos = self.c1_rotation(alpha_angle,
            self.c1_thigh_transformation(0, self.thigh_tibia_transformation(0)))
        thigh_tibia_angle = -atan2(default_gamma_pos[0] - beta_pos[0], -default_gamma_pos[1] + beta_pos[1])  # 0.2211...
        tibia_z_angle = pi - atan2(0.02, -0.16)  # 0.12435499454676124
        try:
            cos_gamma = (pow(self.segment_lengths[2], 2) + pow(self.segment_lengths[1], 2) - pow(lct, 2)) / (
                    2 * self.segment_lengths[1] * self.segment_lengths[2])
            # Avoid running in numerical rounding error
            if (cos_gamma < -1):
                gamma_inner = pi
            else:
                gamma_inner = (acos(cos_gamma))
            gamma_angle = gamma_inner - pi - tibia_z_angle
            if p[2] > 0:
                gamma_angle = pi - gamma_inner - tibia_z_angle

            cos_beta_inner = (pow(self.segment_lengths[1], 2) + pow(lct, 2) - pow(self.segment_lengths[2], 2)) / (
                    2 * self.segment_lengths[1] * lct)
            # Avoid running in numerical rounding error
            if cos_beta_inner > 1:
                h1 = 0
            else:
                h1 = (acos(cos_beta_inner))

            # ee_angle = -atan2(p[2] - beta_pos[2], p[1] - beta_pos[1])
            vector_c1_ee = numpy.linalg.norm(p[0:3] - c1_pos[0:3])
            cos_beta = (pow(lct, 2) + pow(self.segment_lengths[0], 2) - pow(vector_c1_ee, 2)) / (
                    2 * lct * self.segment_lengths[0])
            # Avoid running in numerical rounding error
            if cos_beta < -1.:
                h2 = pi
            else:
                h2 = (acos(cos_beta))
        except ValueError:
            raise ValueError('The provided position (' + str(p_temp[0]) + ', ' + str(p_temp[1]) + ', ' + str(
                p_temp[2]) + ') is not valid for the given geometry for leg ' + self.name)
        if p[2] < 0:
            beta_angle = pi - (h1 + h2 + thigh_tibia_angle)
        else:
            beta_angle = h1 + h2 - pi - thigh_tibia_angle

        # if self.rotation_dir is True:
        #    gamma_angle *= -1
        # else:
        #    beta_angle *= -1
        return numpy.array([alpha_angle, beta_angle, gamma_angle])

    def get_current_angles(self):
        if self.alpha is None or self.beta is None or self.gamma is None:
            return None
        return [self.alpha, self.beta, self.gamma]

    def get_current_targets(self):
        if self.alpha_target is None or self.beta_target is None or self.gamma_target is None:
            return None
        return [self.alpha_target, self.beta_target, self.gamma_target]

    def set_command(self, next_angles):
        # TODO check joint ranges
        rospy.loginfo(
            "set command. angles = " + str(next_angles) + " current angles = " + str(self.get_current_angles()))
        self.alpha_pub.publish(next_angles[0])
        self.beta_pub.publish(next_angles[1])
        self.gamma_pub.publish(next_angles[2])