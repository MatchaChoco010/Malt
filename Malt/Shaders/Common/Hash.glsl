//Copyright (c) 2021 BlenderNPR and contributors. MIT license.

#ifndef COMMON_HASH_GLSL
#define COMMON_HASH_GLSL

//http://www.jcgt.org/published/0009/03/02/

uvec4 pcg4d(uvec4 v)
{
    v = v * 1664525u + 1013904223u;
    v.x += v.y*v.w;
    v.y += v.z*v.x;
    v.z += v.x*v.y;
    v.w += v.y*v.z;
    v ^= v >> 16u;
    v.x += v.y*v.w;
    v.y += v.z*v.x;
    v.z += v.x*v.y;
    v.w += v.y*v.z;
    return v;
}

vec4 pcg4d(vec4 v)
{
    uvec4 u = pcg4d(floatBitsToUint(v));
    return vec4(u) / float(0xffffffffU);
}

vec4 hash(float v){ return pcg4d(vec4(v,0,0,0)); }
vec4 hash(vec2  v){ return pcg4d(vec4(v,0,0)); }
vec4 hash(vec3  v){ return pcg4d(vec4(v,0)); }
vec4 hash(vec4  v){ return pcg4d(v); }

#endif // COMMON_HASH_GLSL
