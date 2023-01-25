#include <string.h>

#include "utils.h"


const char *ad_data_type_to_string(NDDataType_t t)
{
    switch (t) {
        case NDInt8:
            return "int8";
        case NDUInt8:
            return "uint8";
        case NDInt16:
            return "int16";
        case NDUInt16:
            return "uint16";
        case NDInt32:
            return "int32";
        case NDUInt32:
            return "uint32";
        case NDInt64:
            return "int64";
        case NDUInt64:
            return "uint64";
        case NDFloat32:
            return "float32";
        case NDFloat64:
            return "float64";
        default:
            return "x";
    }
}


NDDataType_t ad_data_type_from_string(const char *t)
{
    const char *names[] = {"int8", "uint8", "int16", "uint16",
                           "int32", "uint32", "int64", "uint64",
                           "float32", "float64"};
    NDDataType_t types[] = {NDInt8, NDUInt8, NDInt16, NDUInt16,
                            NDInt32, NDUInt32, NDInt64, NDUInt64,
                            NDFloat32, NDFloat64};
    for (size_t i=0; i < 10; i++) {
        if (strcmp(t, names[i]) == 0)
            return types[i];
    }
    // there is no 'unknown' type in NDDataType_t
    return NDInt8;
}
