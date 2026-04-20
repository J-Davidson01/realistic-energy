module FileCopyWorkload

const sink = Ref{UInt8}(0)

const FILE_COPY_WRITE_AMPLIFICATION = 8
const FILE_COPY_SYNC_INTERVAL = 64 * 1024 * 1024

function write_all(io::IO, buffer::Vector{UInt8}, len::Int)
    written = 0
    while written < len
        written += write(io, @view buffer[(written + 1):len])
    end
    return nothing
end

function workload_file_copy!(src_path::String, dst_path::String, buffer::Vector{UInt8})
    src = open(src_path, "r")
    dst = open(dst_path, "w")

    total_bytes_read = 0
    total_bytes_written = 0
    bytes_since_sync = 0

    while true
        bytes_read = readbytes!(src, buffer)
        if bytes_read == 0
            break
        end

        total_bytes_read += bytes_read

        for _ in 1:FILE_COPY_WRITE_AMPLIFICATION
            write_all(dst, buffer, bytes_read)
            total_bytes_written += bytes_read
            bytes_since_sync += bytes_read

            if bytes_since_sync >= FILE_COPY_SYNC_INTERVAL
                flush(dst)
                Libc.fsync(fd(dst))
                bytes_since_sync = 0
            end
        end
    end

    flush(dst)
    Libc.fsync(fd(dst))

    sink[] ⊻= UInt8(total_bytes_read & 0xff)
    sink[] ⊻= UInt8(total_bytes_written & 0xff)
    sink[] ⊻= buffer[1]

    close(src)
    close(dst)

    return total_bytes_written
end

end # module