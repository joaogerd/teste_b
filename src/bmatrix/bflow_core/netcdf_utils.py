from __future__ import annotations


# NetCDF CDF-5 / 64-bit-data format accepted by MPAS PNetCDF streams.
CDF5_FORMAT = "NETCDF3_64BIT_DATA"


def copy_attrs(src, dst, skip: set[str] | None = None) -> None:
    skip = skip or set()
    for attr in src.ncattrs():
        if attr in skip:
            continue
        try:
            dst.setncattr(attr, src.getncattr(attr))
        except Exception:
            pass


def ensure_dims(src, dst, var) -> None:
    for dim_name in var.dimensions:
        if dim_name not in dst.dimensions:
            src_dim = src.dimensions[dim_name]
            dst.createDimension(dim_name, None if src_dim.isunlimited() else len(src_dim))


def upsert_var(dst, src_var, name: str, data=None):
    if name in dst.variables:
        out = dst.variables[name]
    else:
        kwargs = {}
        fill_value = getattr(src_var, "_FillValue", None)
        if fill_value is not None:
            kwargs["fill_value"] = fill_value
        out = dst.createVariable(name, src_var.dtype, src_var.dimensions, **kwargs)
        copy_attrs(src_var, out, skip={"_FillValue"})
    out[:] = src_var[:] if data is None else data
    return out
