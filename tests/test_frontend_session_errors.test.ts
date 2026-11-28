/**
 * tests/test_frontend_session_errors.test.ts
 *
 * Frontend DoD test suite verifying specific, plain-language error messages
 * and local time rendering for all Daily.co WebRTC session join failure modes (US-14).
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { formatSessionErrorMessage } from '../frontend/src/lib/sessionErrors.ts';

describe('Frontend Session Error Mapping (US-14 / Sprint 4)', () => {
  it('1. formats SESSION_NOT_STARTED with local time', () => {
    const scheduledStartIso = '2026-11-28T18:30:00.000Z';
    const localTimeStr = new Date(scheduledStartIso).toLocaleTimeString([], {
      hour: 'numeric',
      minute: '2-digit',
    });

    // When backend returns error string with timestamp
    const rawError = `425: SESSION_NOT_STARTED: The room opens 10 minutes before the session. It starts at ${scheduledStartIso}.`;
    const res = formatSessionErrorMessage(rawError);

    assert.equal(res.code, 'SESSION_NOT_STARTED');
    assert.equal(res.title, 'Session Has Not Started');
    assert.equal(
      res.description,
      `The room opens 10 minutes before the session. It starts at ${localTimeStr}.`
    );
    assert.ok(res.description.includes(localTimeStr));
  });

  it('1b. formats SESSION_NOT_STARTED using fallback timestamp if not in error string', () => {
    const scheduledStartIso = '2026-11-28T21:00:00.000Z';
    const localTimeStr = new Date(scheduledStartIso).toLocaleTimeString([], {
      hour: 'numeric',
      minute: '2-digit',
    });

    const rawError = new Error('SESSION_NOT_STARTED: The room opens 10 minutes before the session.');
    const res = formatSessionErrorMessage(rawError, scheduledStartIso);

    assert.equal(res.code, 'SESSION_NOT_STARTED');
    assert.equal(
      res.description,
      `The room opens 10 minutes before the session. It starts at ${localTimeStr}.`
    );
  });

  it('2. formats SESSION_WINDOW_EXPIRED with clear closure message', () => {
    const rawError = '410: SESSION_WINDOW_EXPIRED: This session room has expired.';
    const res = formatSessionErrorMessage(rawError);

    assert.equal(res.code, 'SESSION_WINDOW_EXPIRED');
    assert.equal(res.title, 'Session Window Expired');
    assert.equal(
      res.description,
      'This session window has closed. The meeting room is no longer accessible.'
    );
  });

  it('3. formats ESCROW_NOT_HELD explaining credits were settled or refunded', () => {
    const rawError = new Error('400: ESCROW_NOT_HELD: This session escrow is no longer active.');
    const res = formatSessionErrorMessage(rawError);

    assert.equal(res.code, 'ESCROW_NOT_HELD');
    assert.equal(res.title, 'Escrow Inactive');
    assert.equal(
      res.description,
      "This session's escrow is no longer active. The credits have already been settled or refunded."
    );
  });

  it('4. formats UNAUTHORIZED_PARTICIPANT prompting to switch accounts', () => {
    const rawError = '403: UNAUTHORIZED_PARTICIPANT: You are not a participant in this booking.';
    const res = formatSessionErrorMessage(rawError);

    assert.equal(res.code, 'UNAUTHORIZED_PARTICIPANT');
    assert.equal(res.title, 'Access Restricted');
    assert.equal(
      res.description,
      'You are not a registered participant for this mentoring session. Please switch to the account that booked or is mentoring this session.'
    );
  });

  it('5. formats ROOM_CREATION_FAILED reassuring user was not charged', () => {
    const rawError = '503: ROOM_CREATION_FAILED: Failed to create video room. Booking cancelled and escrow refunded.';
    const res = formatSessionErrorMessage(rawError);

    assert.equal(res.code, 'ROOM_CREATION_FAILED');
    assert.equal(res.title, 'Video Room Unavailable');
    assert.equal(
      res.description,
      "We couldn't create the video room. You were not charged."
    );
  });

  it('6. formats network and server unreachable errors', () => {
    const networkErrors = [
      new Error('Failed to fetch'),
      new Error('NetworkError when attempting to fetch resource.'),
      'net::ERR_CONNECTION_REFUSED',
      '502: Bad Gateway',
      '504: Gateway Timeout',
      'Network or server unreachable',
    ];

    for (const err of networkErrors) {
      const res = formatSessionErrorMessage(err);
      assert.equal(res.code, 'NETWORK_ERROR');
      assert.equal(res.title, 'Connection Error');
      assert.equal(
        res.description,
        'Network or server unreachable. Please check your connection and try again.'
      );
    }
  });

  it('7. provides a clean fallback message for unexpected error strings', () => {
    const res = formatSessionErrorMessage('Unexpected edge condition');
    assert.equal(res.code, 'UNKNOWN_ERROR');
    assert.equal(res.title, 'Unable to Enter Room');
    assert.equal(res.description, 'Unexpected edge condition');
  });
});
