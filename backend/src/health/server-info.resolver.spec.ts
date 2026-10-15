import { ServerInfoResolver } from './server-info.resolver';
import { SERVER_PROTOCOL } from './protocol';

// The Unreal twin S08ClientProtocol is compared on the host by tools/s08/test_protocol_version.py
// (the backend container mounts backend/ only).
describe('ServerInfoResolver (GD-053)', () => {
  it('answers the protocol number', () => {
    expect(new ServerInfoResolver().serverInfo()).toEqual({ protocol: SERVER_PROTOCOL });
  });
});
