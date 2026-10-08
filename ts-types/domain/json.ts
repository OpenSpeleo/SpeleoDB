/** Arbitrary parsed JSON; endpoint records define their own finite fields. */
export type JSONValue = null | boolean | number | string | JSONContainer;

export type JSONContainer = JSONObject | JSONValue[];

export interface JSONObject {
    [key: string]: JSONValue;
}
