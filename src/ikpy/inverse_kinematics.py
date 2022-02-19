# coding= utf8
import scipy.optimize
import numpy as np
from . import logs


ORIENTATION_COEFF = 1.


def inverse_kinematic_optimization(chain, target_frame, starting_nodes_angles, regularization_parameter=None, max_iter=None, orientation_mode=None, no_position=False, optimization_method='L-BFGS-B'):
    """
    Computes the inverse kinematic on the specified target with an optimization method

    Parameters
    ----------
    chain: ikpy.chain.Chain
        The chain used for the Inverse kinematics.
    target_frame: numpy.array
        The desired target.
    starting_nodes_angles: numpy.array
        The initial pose of your chain.
    regularization_parameter: float
        The coefficient of the regularization.
    max_iter: int
        Maximum number of iterations for the optimisation algorithm.
    orientation_mode: str
        Orientation to target. Choices:
        * None: No orientation
        * "X": Target the X axis
        * "Y": Target the Y axis
        * "Z": Target the Z axis
        * "all": Target the three axes
    no_position: bool
        Do not optimize against position
    optimization_method: str
        Optimization method to use. Defaults to 'L-BFGS-B'
    """
    # Begin with the position
    target = target_frame[:3, -1]

    # Initial function call when optimizing
    def optimize_basis(x):
        # y = np.append(starting_nodes_angles[:chain.first_active_joint], x)
        y = chain.active_to_full(x, starting_nodes_angles)
        fk = chain.forward_kinematics(y)

        return fk

    # Compute error to target
    def optimize_target_function(fk):
        target_error = fk[:3, -1] - target

        # We need to return the fk, it will be used in a later function
        # This way, we don't have to recompute it
        return target_error

    if orientation_mode is None:
        if no_position:
            raise ValueError("Unable to optimize against neither position or orientation")

        else:
            def optimize_function(x):
                fk = optimize_basis(x)
                target_error = optimize_target_function(fk)
                return target_error
    else:
        # Only get the first orientation vector
        if orientation_mode == "X":
            target_orientation = target_frame[:3, 0]

            def get_orientation(fk):
                return fk[:3, 0]

        elif orientation_mode == "Y":
            target_orientation = target_frame[:3, 1]

            def get_orientation(fk):
                return fk[:3, 1]

        elif orientation_mode == "Z":
            target_orientation = target_frame[:3, 2]

            def get_orientation(fk):
                return fk[:3, 2]

        elif orientation_mode == "all":
            target_orientation = target_frame[:3, :3]

            def get_orientation(fk):
                return fk[:3, :3]
        else:
            raise ValueError("Unknown orientation mode: {}".format(orientation_mode))

        if not no_position:
            def optimize_function(x):
                # Note: We have to 
                fk = optimize_basis(x)

                target_error = optimize_target_function(fk)
                orientation_error = (get_orientation(fk) - target_orientation).ravel()

                # Put more pressure on optimizing the distance to target, to avoid being stuck in a local minimum where the orientation is perfectly reached, but the target is nowhere to be reached
                total_error = np.concatenate([target_error, ORIENTATION_COEFF * orientation_error])

                return total_error
        else:
            def optimize_function(x):
                fk = optimize_basis(x)

                orientation_error = (get_orientation(fk) - target_orientation).ravel()
                total_error = orientation_error

                return total_error

    if starting_nodes_angles is None:
        raise ValueError("starting_nodes_angles must be specified")

    # If a regularization is selected
    if regularization_parameter is not None:
        def optimize_total(x):
            regularization = np.linalg.norm(x - chain.active_from_full(starting_nodes_angles))
            return optimize_function(x) + regularization_parameter * regularization
    else:
        optimize_total = optimize_function

    # Compute bounds
    real_bounds = [link.bounds for link in chain.links]
    # real_bounds = real_bounds[chain.first_active_joint:]
    real_bounds = np.moveaxis(chain.active_from_full(real_bounds), -1, 0)

    logs.logger.warning("Bounds: {}".format(real_bounds))

    if max_iter is not None:
        logs.logger.info("max_iter is not used anymore in the IK, using it as a parameter will raise an exception in the future")

    # least squares optimization
    res = scipy.optimize.least_squares(optimize_total, chain.active_from_full(starting_nodes_angles), bounds=real_bounds)

    if res.status != -1:
        logs.logger.warning("Inverse kinematic optimisation OK, termination status: {}".format(res.status))
    else:
        logs.logger.warning("Inverse kinematic optimisation returned an error: termination status: {}".format(res.status))

    return chain.active_to_full(res.x, starting_nodes_angles)
