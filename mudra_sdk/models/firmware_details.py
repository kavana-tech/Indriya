class FirmwareDetails:

    __slots__ = ()

    def __new__(cls):
        raise TypeError("%s cannot be instantiated" % cls.__name__)

    #: Stable firmware version for Mudra Band (DFU, device info, cloud details).
    STABLE_VERSION_MUDRA = "6.0.12.1"

    #: Release / MDK target firmware version for update checks.
    RELEASE_VERSION_MUDRA = "6.0.11.3"
