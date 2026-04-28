module FileCopyWorkload

const sink = Ref{UInt8}(0)

const FILE_COPY_WRITE_AMPLIFICATION = 8
const FILE_COPY_SYNC_INTERVAL = 64 * 1024 * 1024

function write_all(io::IO, buffer::AbstractVector{UInt8})
    written = 0
    len = length(buffer)
    while written < len
        written += write(io, @view buffer[(written + 1):end])
    end
    return nothing
end

function workload_file_copy!(dst::IO, buffer::AbstractVector{UInt8})
    bytes_since_sync = 0
    buffer_len = length(buffer)

    for _ in 1:FILE_COPY_WRITE_AMPLIFICATION
        write_all(dst, buffer)
        bytes_since_sync += buffer_len

        if bytes_since_sync >= FILE_COPY_SYNC_INTERVAL
            flush(dst)
            Libc.fsync(fd(dst))
            bytes_since_sync = 0
        end
    end

    flush(dst)
    Libc.fsync(fd(dst))

    sink[] ⊻= UInt8(buffer_len & 0xff)
    sink[] ⊻= buffer[1]

    return 1
end

end # module