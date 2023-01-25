# Protocol between AD plugin and worker program
- The AD plugin provides a unix socket to talk to the workers
- Every message is a JSON in which the root element is an object.
- The frame data is passed in shared memory

## Handshake
- Once a worker connects to the AD plugin socket, it will send a message to
  indicate its name, e.g.: `{"class_name" : "gauss_fit"}`
  If the server doesn't expect that type of worker, it will send an error
  message and close the connection.
  If the server expects that worker, it will send a message indicating the name
  of the shared memory file (which will be present in /dev/shm), e.g.
  `{"ok": true, "shm_name": "shm_file1"}`,

## Updating parameters
- The worker can update AD parameters by sending a message with a "vars" object,
  e.g. `{"vars": {"sModel": "model1", "iVersion": 1, "dTemperature": 25.0}}`
- The name of each parameters should indicate its type in the first letter,
  'i' for integer, 'd' for double or 's' for string.
- The AD plugin can update worker parameters by sending the same type of message

## Sending frames
- The AD plugin will tell the worker to process a frame by sending a message
  like this:
`{"frame_dims": (1024, 768), "data_type": "uint8", "frame_loc": 0}`
- "data\_type" indicates the data type, first part indicates if is signed
integer(int), unsigned integer(uint) or float(float), then follows a number
indicating bits of data type
- "frame\_loc" indicate the offset of the frame data from the start of shared
memory

## Receiving frames
- The worker will notify the AD plugin of a frame by sending a message
 like this:
`{"push_frame": true, "frame_dims": (1024, 768), "data_type": "uint8"}`

if data\_type or frame\_dims is missing, it will be assumed to be the same
as input frame
- Given that the same shared memory region is used for the output frame, the
worker can produce only frames of the same size or less than the input frame.
- If the worker doesn't want the frame to be pushed, it will have the field
"push\_frame" set to false, this also let the AD plugin know that frame
can be released, e.g.
`{"push_frame": false}`
- The message can contain the field "vars" to update parameters
- The message can contain the field "attrs" to associate attributes to the frame
- New attributes can only be integer, double or string
